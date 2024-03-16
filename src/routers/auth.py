from fastapi import APIRouter, Body, HTTPException, status, Depends, Query, Request, Response, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.routing import APIRoute
from pydantic import field_validator, Field, ValidationError
from passlib.context import CryptContext
from passlib.pwd import genword  # type: ignore
from jose import jwt, JWTError
from typing import Annotated, Any, Callable, Coroutine, Literal
from models import User, FromDBModel, CamelModel
from database import DBConnectionDep, DBConnection
from utils import print_exception, get_json_error_resonse
import settings
from datetime import datetime, timedelta, timezone
import re


password_context = CryptContext(schemes=['bcrypt'])


class Credentials(CamelModel):
    username: Annotated[str, Field(
        min_length=1,
        max_length=20,
        description='Only letters, numbers, spaces, periods, hyphens and underscores are allowed. ([a-zA-Z0-9_\\-. ])',
    )]
    password: Annotated[str, Field(
        min_length=12,
        max_length=1024,
        description=(
            'Must have 1 lowercase, uppercase, and number. '
            'Must not contain the same character consecutively more than twice. '
            'Must not contain consecutive numbers in increasing/decreasing order more than twice.'
        ),
        examples=['ValidPassword1']
    )]


class SignUpCredentials(Credentials):
    @field_validator('username')
    @staticmethod
    def validate_username(username: str) -> str:
        if len(username) > 20:
            raise ValueError('Username is too long. Max length: 20.')

        valid_characters = r'^[a-zA-Z0-9_\-. ]+$'

        if not re.match(valid_characters, username):
            raise ValueError('Invalid characters. Only letters, numbers, spaces, periods, hyphens and underscores are allowed. ([a-zA-Z0-9_\\-. ])')

        return username

    @field_validator('password')
    @staticmethod
    def validate_password(password: str) -> str:
        if len(password) < 12:
            raise ValueError('Password too short. Min length: 12.')

        one_lowercase = r'.*[a-z].*'

        if not re.match(one_lowercase, password):
            raise ValueError('Password must include at least 1 lowercase letter.')

        one_uppercase = r'.*[A-Z].*'

        if not re.match(one_uppercase, password):
            raise ValueError('Password must include at least 1 uppercase letter.')

        one_number = r'.*[0-9].*'

        if not re.match(one_number, password):
            raise ValueError('Password must include at least 1 number.')

        same_consecutive_character = r'.*([a-zA-Z0-9._\- ])\1{2}.*'

        if re.match(same_consecutive_character, password):
            raise ValueError('Password must not contain the same character consecutively more than twice.')

        numbers_regex = r'([0-9]+)'
        password_numbers: list[str] = re.findall(numbers_regex, password)

        for digits in password_numbers:

            if len(digits) <= 2:
                continue

            for i in range(len(digits) - 2):
                if int(digits[i]) + 1 == int(digits[i + 1]) and int(digits[i + 1]) + 1 == int(digits[i + 2]):
                    raise ValueError('Password must not contain consecutive numbers in increasing order more than twice.')

                if int(digits[i]) - 1 == int(digits[i + 1]) and int(digits[i + 1]) - 1 == int(digits[i + 2]):
                    raise ValueError('Password must not contain consecutive numbers in decreasing order more than twice.')

        return password


class DBUser(FromDBModel):
    id: int
    password_hash: str


class Tokens(CamelModel):
    access_token: Annotated[str, Field(
        description=(
            'Utilize this token for authentication when accessing secured endpoints. '
            'It has an expiration time of %d minutes.' % settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )]
    refresh_token: Annotated[str, Field(
        description=(
            'Utilize this token to obtain a new token pair, granting continued access to protected endpoints. '
            'It has an expiration time of %d days.' % settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    )]
    device_id: Annotated[int, Field(
        description=(
            'A unique device identifier per user. '
            'Include this ID when obtaining a new token pair using credentials to avoid creating a new branch of RefreshTokens.'
        )
    )]


class AccessTokenClaims(FromDBModel):
    sub: str
    type: Literal['access']
    exp: float


class RefreshTokenClaims(FromDBModel):
    sub: str
    token_id: int
    family_id: int
    device_id: int
    type: Literal['refresh']
    exp: float


class DecodedRefreshToken(FromDBModel):
    token: str
    claims: RefreshTokenClaims


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, key=settings.SECRET_KEY, algorithms=settings.JWT_ALGORITHM)

    except JWTError:
        return None


def encode_token(claims: dict[str, Any]) -> str | None:
    try:
        return jwt.encode(claims, key=settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    except JWTError:
        return None


def refresh_tokens_(db: DBConnection, refresh_token: str) -> tuple[Tokens | None, str]:
    refresh_token_claims = decode_token(refresh_token)

    if refresh_token_claims is None:
        return None, 'Could not decode refresh token.'

    if refresh_token_claims['type'] != 'refresh':
        return None, 'Token type is not "refresh".'

    user_id = int(refresh_token_claims['sub'])
    device_id: int = refresh_token_claims['device_id']

    row = db.fetch_one(
        'SELECT token_id, family_id, is_invalidated '
        'FROM auth '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': user_id, 'device_id': device_id}
    )

    if row is None:
        return None, 'Could not get token claims from DB.'

    if row.is_invalidated:
        return None, 'Refresh token is invalidated.'

    token_id: int = row.token_id
    family_id: int = row.family_id

    if family_id == refresh_token_claims['family_id'] and token_id != refresh_token_claims['token_id']:
        db.execute(
            'UPDATE auth '
            'SET is_invalidated = TRUE '
            'WHERE user_id = :user_id AND device_id = :device_id;',
            {'user_id': user_id, 'device_id': device_id},
        )

        return None, 'Old token ID.'

    if family_id != refresh_token_claims['family_id']:
        return None, 'Token family ID does not match.'

    token_id += 1

    new_access_token = encode_token({
        'sub': str(user_id),
        'type': 'access',
        'exp': (datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
    })

    new_refresh_token = encode_token({
        'sub': str(user_id),
        'token_id': token_id,
        'family_id': family_id,
        'device_id': device_id,
        'type': 'refresh',
        'exp': (datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
    })

    if new_access_token is None or new_refresh_token is None:
        return None, 'Could not generated access or/and refresh token/s.'

    db.execute(
        'UPDATE auth '
        'SET token_id = :token_id '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'token_id': token_id, 'user_id': user_id, 'device_id': device_id},
    )

    return Tokens(access_token=new_access_token, refresh_token=new_refresh_token, device_id=device_id), ''


def generate_tokens_(db: DBConnection, user_id: int, device_id: int | None = None) -> tuple[Tokens | None, str]:
    is_first_login = True
    family_id = 0

    if device_id is None:
        row = db.fetch_one(
            'SELECT MAX(device_id) as last_device_id '
            'FROM auth '
            'WHERE user_id = :user_id;',
            {'user_id': user_id}
        )

        if row is None or row.last_device_id is None:
            device_id = 0
        else:
            device_id = int(row.last_device_id) + 1

    else:
        row = db.fetch_one(
            'SELECT family_id '
            'FROM auth '
            'WHERE user_id = :user_id AND device_id = :device_id;',
            {'user_id': user_id, 'device_id': device_id}
        )

        if row is None:
            return None, 'Could not get family_id from DB.'

        is_first_login = False
        family_id = row.family_id + 1

    new_access_token = encode_token({
        'sub': str(user_id),
        'type': 'access',
        'exp': (datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
    })

    new_refresh_token = encode_token({
        'sub': str(user_id),
        'token_id': 0,
        'family_id': family_id,
        'device_id': device_id,
        'type': 'refresh',
        'exp': (datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
    })

    if new_access_token is None or new_refresh_token is None:
        return None, 'Could not generated access or/and refresh token/s.'

    if is_first_login:
        db.execute(
            'INSERT INTO auth (user_id, token_id, family_id, device_id, is_invalidated) '
            'VALUES (:user_id, 0, :family_id, :device_id, FALSE);',
            {
                'user_id': user_id,
                'family_id': family_id,
                'device_id': device_id
            },
        )

    else:
        db.execute(
            'UPDATE auth '
            'SET token_id = 0, '
            '    family_id = :family_id, '
            '    is_invalidated = FALSE '
            'WHERE user_id = :user_id AND device_id = :device_id;',
            {
                'family_id': family_id,
                'user_id': user_id,
                'device_id': device_id
            },
        )

    return Tokens(access_token=new_access_token, refresh_token=new_refresh_token, device_id=device_id), ''


def get_db_user(db: DBConnection, username: str) -> DBUser | None:
    row = db.fetch_one(
        'SELECT id, password_hash '
        'FROM users '
        'WHERE username = :username;',
        {'username': username}
    )

    if row is None:
        return None

    return DBUser.model_validate(row)


class UnauthorizedException(HTTPException):
    reason: str

    def __init__(self, reason: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        self.reason = reason


get_access_token = HTTPBearer(scheme_name='Bearer Access Token')


class RefreshTokenBody(CamelModel):
    refresh_token: str


def authenticate_refresh_token(refresh_token_body: Annotated[RefreshTokenBody, Body()]) -> DecodedRefreshToken:
    refresh_token_claims = decode_token(refresh_token_body.refresh_token)

    if refresh_token_claims is None:
        raise UnauthorizedException('Could not decode refresh token.')

    try:
        claims = RefreshTokenClaims.model_validate(refresh_token_claims)
    except ValidationError:
        raise UnauthorizedException('Could not validate refresh token claims.')

    return DecodedRefreshToken(token=refresh_token_body.refresh_token, claims=claims)


AuthenticatedRefreshToken = Annotated[DecodedRefreshToken, Depends(authenticate_refresh_token)]


def authenticate_user(authorization_header: Annotated[HTTPAuthorizationCredentials, Depends(get_access_token)]) -> int:
    access_token_claims = decode_token(authorization_header.credentials)

    if access_token_claims is None:
        raise UnauthorizedException('Could not decode access token.')

    try:
        AccessTokenClaims.model_validate(access_token_claims)
    except ValidationError:
        raise UnauthorizedException('Could not validate access token claims.')

    return int(access_token_claims['sub'])


class RouteErrorHandler(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)

            except Exception as exception:
                if settings.DEBUG:
                    print_exception(exception)

                raise exception

        return custom_route_handler


AuthenticatedUserID = Annotated[int, Depends(authenticate_user)]

username_in_use_exception = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        'msg': 'Username already in use.',
        'username_in_use': True
    }
)

router = APIRouter(tags=['Authentication'], route_class=RouteErrorHandler)


@router.post('/signup', response_model=User, status_code=status.HTTP_201_CREATED, responses={
    status.HTTP_409_CONFLICT: get_json_error_resonse(example={'detail': username_in_use_exception.detail})
})
def register_user(credentials: Annotated[SignUpCredentials, Body()], db: DBConnectionDep) -> User:
    row = db.fetch_one(
        'SELECT id '
        'FROM users '
        'WHERE username = :username;',
        credentials.model_dump()
    )

    if row is not None:
        raise username_in_use_exception

    user = {
        "username": credentials.username,
        "password_hash": password_context.hash(credentials.password)
    }

    db.execute(
        'INSERT INTO users (username, password_hash) '
        'VALUES (:username, :password_hash);',
        user,
    )

    return User(**user)


@router.post('/tokens', response_model=Tokens)
def generate_tokens(
    credentials: Annotated[Credentials, Body()],
    db: DBConnectionDep,
    device_id: Annotated[int | None, Query(description=(
        'A unique device identifier per user. '
        'Include this ID to avoid creating a new branch of RefreshTokens.'
    ))] = None
) -> Tokens:
    db_user = get_db_user(db, credentials.username)

    if db_user is None:
        raise UnauthorizedException('Could not get user from DB.')

    is_verified, new_password_hash = password_context.verify_and_update(credentials.password, db_user.password_hash)

    if not is_verified:
        raise UnauthorizedException('Passwords do not match.')

    if new_password_hash is not None:
        db_user.password_hash = new_password_hash

        db.execute(
            'UPDATE users '
            'SET password_hash = :password_hash '
            'WHERE id = :id;',
            db_user.model_dump(),
        )

    tokens, error_msg = generate_tokens_(db, db_user.id, device_id)

    if tokens is None:
        raise UnauthorizedException('Could not generate tokens: ' + error_msg)

    return tokens


@router.post('/refresh', response_model=Tokens)
def refresh_tokens(decoded_refresh_token: AuthenticatedRefreshToken, db: DBConnectionDep) -> Tokens:
    '''
    Each refresh token is uniquely identified by a token id, token family id, and device id.
    When a refresh occurs, the new refresh token is issued with a different token id while retaining the same family id and device id.
    Refreshing a token with the same token id and family id extends the user's session.
    However, if a token with the same token id and a different family id is used for refresh, the request is rejected, ensuring security.
    Furthermore, if a refresh is attempted on a token belonging to a different branch of token families associated with the same device id, all tokens are invalidated, requiring the user to re-login for enhanced security and access control.
    '''
    tokens, error_msg = refresh_tokens_(db, decoded_refresh_token.token)

    if tokens is None:
        raise UnauthorizedException('Could not refresh tokens: ' + error_msg)

    return tokens


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(decoded_refresh_token: AuthenticatedRefreshToken, db: DBConnectionDep) -> None:
    '''
    Invalidate a session (refresh token family).
    '''
    db.execute(
        'UPDATE auth '
        'SET is_invalidated = TRUE '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': int(decoded_refresh_token.claims.sub), 'device_id': decoded_refresh_token.claims.device_id},
    )


@router.post('/logout/{device_id}', status_code=status.HTTP_204_NO_CONTENT)
def logout_device(credentials: Annotated[Credentials, Body()], device_id: Annotated[int, Path()], db: DBConnectionDep) -> None:
    '''
    Invalidate a session (device id) with credentials. Specially used for logout test accounts.
    '''
    db_user = get_db_user(db, credentials.username)

    if db_user is None:
        raise UnauthorizedException('Could not get user from DB.')

    if not password_context.verify(credentials.password, db_user.password_hash):
        raise UnauthorizedException('Passwords do not match.')

    db.execute(
        'UPDATE auth '
        'SET is_invalidated = TRUE '
        'WHERE user_id = :user_id AND device_id = :device_id;',
        {'user_id': db_user.id, 'device_id': device_id},
    )


@router.post('/testaccount', response_model=Credentials, status_code=status.HTTP_201_CREATED)
def generate_test_account(db: DBConnectionDep) -> Credentials:
    '''
    Generates a new test user for accessing protected endpoints without the need for signup.
    '''
    new_test_number = 0

    rows = db.fetch_many(
        'SELECT username '
        'FROM users '
        'WHERE username LIKE "#testaccount%";'
    )

    if rows:
        numbers_pattern = re.compile(r'\d+')
        new_test_number = max((
            int(number.group())
            for row in rows
            if (number := numbers_pattern.search(row.username)) is not None
        )) + 1

    new_credentials = Credentials(username=f'#testaccount{new_test_number}', password=genword(length=20))  # type: ignore

    db.execute(
        'INSERT INTO users (username, password_hash) '
        'VALUES (:username, :password_hash);',
        {
            'username': new_credentials.username,
            'password_hash': password_context.hash(new_credentials.password)
        },
    )

    return new_credentials
