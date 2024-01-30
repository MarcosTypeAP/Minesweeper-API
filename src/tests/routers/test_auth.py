from fastapi.testclient import TestClient
from pydantic import ValidationError
from routers.auth import (
    SignUpCredentials,
    generate_tokens_,
    refresh_tokens_,
    AccessTokenClaims,
    RefreshTokenClaims,
    decode_token,
    password_context,
    Tokens
)
from database import DBConnection
from freezegun import freeze_time
from conftest import TestUser
from datetime import datetime, timedelta
from typing import Callable, Any
import functools
import settings

AUTH_URL = '/api/auth'
SIGNUP_URL = AUTH_URL + '/signup'
LOGIN_URL = AUTH_URL + '/tokens'
REFRESH_URL = AUTH_URL + '/refresh'
LOGOUT_URL = AUTH_URL + '/logout'
TEST_ACCOUNT_URL = AUTH_URL + '/testaccount'


def test_username_validation() -> None:
    def is_valid(username: str) -> bool:
        try:
            SignUpCredentials(username=username, password='ValidPassword1')
            return True

        except ValidationError:
            return False

    assert not is_valid('')
    assert not is_valid('username_larger_than_20_characters')
    assert not is_valid('#')
    assert is_valid('aZ1_.- ')


def test_password_validation() -> None:
    def is_valid(password: str) -> bool:
        try:
            SignUpCredentials(username='ValidUsername', password=password)
            return True

        except ValidationError:
            return False

    assert not is_valid('')
    assert not is_valid('lessthan12')
    assert not is_valid('morethantwelve')
    assert not is_valid('62643572342362')
    assert not is_valid('62643572342362a')
    assert not is_valid('Oneuppercase')
    assert is_valid('1Numberpassword')
    assert not is_valid('3ConsecutiveIncreasingOrder456')
    assert not is_valid('3ConsecutiveDecreasingOrder876')
    assert not is_valid('3SameCharactersAAA')
    assert not is_valid('3SameCharactersAAA')


@freeze_time('2000-01-01 00:00:00')
def test_generate_tokens(user: TestUser, db: DBConnection) -> None:
    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    claims = decode_token(tokens.access_token)
    assert claims is not None
    access_token_claims = AccessTokenClaims.model_validate(claims)

    claims = decode_token(tokens.refresh_token)
    assert claims is not None
    refresh_token_claims = RefreshTokenClaims.model_validate(claims)

    access_token_exp = (datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
    assert access_token_claims.exp == access_token_exp
    assert access_token_claims.sub == str(user.id)

    refresh_token_exp = (datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
    assert refresh_token_claims.exp == refresh_token_exp
    assert refresh_token_claims.sub == str(user.id)
    assert refresh_token_claims.token_id == 0
    assert refresh_token_claims.family_id == 0
    assert refresh_token_claims.device_id == 0

    row = db.fetch_one(
        'SELECT token_id, family_id, is_invalidated '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user.id, 'device_id': refresh_token_claims.device_id}
    )

    assert row is not None
    assert refresh_token_claims.token_id == row.token_id
    assert refresh_token_claims.family_id == row.family_id
    assert not row.is_invalidated

    # Re-Generate tokens

    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    refresh_token_claims = RefreshTokenClaims.model_validate(
        decode_token(tokens.refresh_token)
    )

    assert refresh_token_claims.token_id == 0
    assert refresh_token_claims.family_id == 0
    assert refresh_token_claims.device_id == 1

    # Re-Generate tokens with device ID

    tokens, _ = generate_tokens_(db, user.id, refresh_token_claims.device_id)
    assert tokens is not None

    refresh_token_claims = RefreshTokenClaims.model_validate(
        decode_token(tokens.refresh_token)
    )

    assert refresh_token_claims.token_id == 0
    assert refresh_token_claims.family_id == 1
    assert refresh_token_claims.device_id == 1

    # Each token family is separated by device id
    # The different branches of families cannot interact with each other

    tokens1, _ = generate_tokens_(db, user.id)
    assert tokens1 is not None
    tokens2, _ = generate_tokens_(db, user.id)
    assert tokens2 is not None
    
    tokens1, _ = generate_tokens_(db, user.id, tokens1.device_id)
    assert tokens1 is not None

    refresh_token_2_claims = decode_token(tokens2.refresh_token)
    assert refresh_token_2_claims is not None

    row = db.fetch_one(
        'SELECT family_id, token_id '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user.id, 'device_id': tokens2.device_id}
    )
    assert row is not None

    assert refresh_token_2_claims['token_id'] == row.token_id
    assert refresh_token_2_claims['family_id'] == row.family_id


@freeze_time('2000-01-01 00:00:00')
def test_refresh_tokens(user: TestUser, db: DBConnection) -> None:
    tokens1, _ = generate_tokens_(db, user.id)
    assert tokens1 is not None

    tokens2, _ = refresh_tokens_(db, tokens1.refresh_token)
    assert tokens2 is not None

    claims = decode_token(tokens2.access_token)
    assert claims is not None
    access_token_claims2 = AccessTokenClaims.model_validate(claims)

    claims = decode_token(tokens2.refresh_token)
    assert claims is not None
    refresh_token_claims2 = RefreshTokenClaims.model_validate(claims)

    access_token_exp = (datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
    assert access_token_claims2.exp == access_token_exp
    assert access_token_claims2.sub == str(user.id)

    refresh_token_exp = (datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
    assert refresh_token_claims2.exp == refresh_token_exp
    assert refresh_token_claims2.sub == str(user.id)
    assert refresh_token_claims2.token_id == 1
    assert refresh_token_claims2.family_id == 0
    assert refresh_token_claims2.device_id == 0

    # Token rotation

    tokens3, _ = refresh_tokens_(db, tokens2.refresh_token)
    assert tokens3 is not None

    refresh_token_claims3 = RefreshTokenClaims.model_validate(
        decode_token(tokens3.refresh_token)
    )

    assert refresh_token_claims3.token_id == 2
    assert refresh_token_claims3.family_id == 0
    assert refresh_token_claims3.device_id == 0

    # Cannot use old token with same family

    tokens4, _ = refresh_tokens_(db, tokens2.refresh_token)
    assert tokens4 is None

    row = db.fetch_one(
        'SELECT is_invalidated '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user.id, 'device_id': refresh_token_claims3.device_id}
    )
    assert row is not None
    assert row.is_invalidated

    # Cannot use the latest token after using old token

    tokens3, _ = refresh_tokens_(db, tokens2.refresh_token)
    assert tokens3 is None

    # Must re-generate tokens
    # New tokens must have different family
    # And the account must not be invalidated

    tokens5, _ = generate_tokens_(db, user.id, refresh_token_claims3.device_id)
    assert tokens5 is not None

    refresh_token_claims5 = RefreshTokenClaims.model_validate(
        decode_token(tokens5.refresh_token)
    )

    assert refresh_token_claims5.token_id == 0
    assert refresh_token_claims5.family_id == 1
    assert refresh_token_claims5.device_id == 0

    row = db.fetch_one(
        'SELECT is_invalidated '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user.id, 'device_id': refresh_token_claims3.device_id}
    )
    assert row is not None
    assert not row.is_invalidated

    # Refreshing old tokens with different family must not invalidate account

    tokens6, _ = refresh_tokens_(db, tokens2.refresh_token)
    assert tokens6 is None

    row = db.fetch_one(
        'SELECT is_invalidated '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user.id, 'device_id': refresh_token_claims3.device_id}
    )
    assert row is not None
    assert not row.is_invalidated


def test_signup(client: TestClient, db: DBConnection) -> None:
    res = client.post(SIGNUP_URL)
    assert res.status_code == 422

    res = client.post(SIGNUP_URL, json={'username': '#InvalidUsername', 'password': 'ValidPassword1'})
    assert res.status_code == 422

    res = client.post(SIGNUP_URL, json={'username': 'ValidUsername', 'password': 'InvalidPassword'})
    assert res.status_code == 422

    credentials = {'username': 'TestUsername', 'password': 'ValidPassword1'}

    res = client.post(SIGNUP_URL, json=credentials)
    assert res.status_code == 201

    row = db.fetch_one(
        'SELECT id, username '
        'FROM users '
        'WHERE username = :username;',
        credentials
    )

    assert row is not None
    assert row.username == credentials['username']

    res = client.post(SIGNUP_URL, json=credentials)
    assert res.status_code == 409


#  @decorator.decorator
#  def change_password_context(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    #  initial_config = password_context.to_dict()
    #  password_context.update(schemes=password_context.schemes() + ('md5_crypt',), deprecated=['auto'])

    #  result = func(*args, **kwargs)

    #  password_context.load(initial_config)

    #  return result


def change_password_context(func: Callable[..., Any]):
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        initial_config = password_context.to_dict()
        password_context.update(schemes=password_context.schemes() + ('md5_crypt',), deprecated=['auto'])

        result = func(*args, **kwargs)

        password_context.load(initial_config)

        return result

    return wrapper


@freeze_time('2000-01-01 00:00:00')
@change_password_context
def test_login(client: TestClient, user: TestUser, db: DBConnection) -> None:
    res = client.post(LOGIN_URL)
    assert res.status_code == 422

    wrong_credentials = {'username': user.username, 'password': 'WrongPassword1'}

    res = client.post(LOGIN_URL, json=wrong_credentials)
    assert res.status_code == 401

    right_credentials = {'username': user.username, 'password': user.password}

    # Logged in on many devices
    tokens, _ = generate_tokens_(db, user.id)
    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    res = client.post(LOGIN_URL, json=right_credentials, params={'device_id': tokens.device_id})
    assert res.status_code == 200

    body = res.json()
    assert 'accessToken' in body
    assert 'refreshToken' in body
    assert 'deviceId' in body
    assert body['deviceId'] == tokens.device_id

    # Re-Hash password if deprecated hashing algorithm (md5 is used for TestUser)

    row = db.fetch_one(
        'SELECT password_hash '
        'FROM users '
        'WHERE id = :user_id;',
        {'user_id': user.id}
    )
    assert row is not None
    assert row.password_hash != user.password_hash


def test_refresh_tokens_endpoint(client: TestClient, user: TestUser, fake_tokens: Tokens, db: DBConnection) -> None:
    res = client.post(REFRESH_URL)
    assert res.status_code == 422

    res = client.post(REFRESH_URL, json={'refreshToken': fake_tokens.refresh_token})
    assert res.status_code == 401

    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    res = client.post(REFRESH_URL, json={'refreshToken': tokens.refresh_token})
    assert res.status_code == 200

    Tokens.model_validate(res.json())


def test_logout(client: TestClient, user: TestUser, fake_tokens: Tokens, db: DBConnection) -> None:
    res = client.post(LOGOUT_URL)
    assert res.status_code == 422

    res = client.post(LOGOUT_URL, json={'refreshToken': fake_tokens.refresh_token})
    assert res.status_code == 401

    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    res = client.post(LOGOUT_URL, json={'refreshToken': tokens.refresh_token})
    assert res.status_code == 204

    tokens, _ = refresh_tokens_(db, tokens.refresh_token)
    assert tokens is None


def test_create_test_account(client: TestClient, db: DBConnection) -> None:
    res = client.post(TEST_ACCOUNT_URL)
    assert res.status_code == 201

    body = res.json()
    assert 'username' in body
    assert body['username'].startswith('#testaccount')
    assert body['username'].endswith(tuple((str(i) for i in range(10))))
    assert 'password' in body

    is_username_invalid = False
    try:
        SignUpCredentials.model_validate(body)
    except ValidationError:
        is_username_invalid = True

    assert is_username_invalid

    row = db.fetch_one(
        'SELECT id, password_hash '
        'FROM users '
        'WHERE username = :username;',
        body
    )
    assert row is not None

    assert password_context.verify(body['password'], row.password_hash)

    res = client.post(TEST_ACCOUNT_URL)
    assert res.status_code == 201

    assert res.json()['username'] != body['username']
    assert res.json()['password'] != body['password']

    tokens, _ = generate_tokens_(db, row.id)
    assert tokens is not None
