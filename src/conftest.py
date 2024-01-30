from fastapi.testclient import TestClient
from passlib.hash import md5_crypt
from dataclasses import dataclass
from httpx import Response
from contextlib import contextmanager
from pydantic import BaseModel
from jose import jwt
import pytest

# App
from database import DBConnection, get_db_connection, TestDatabaseManager
from migrate import run_all_migrations
from routers.auth import Tokens
from routers.auth import generate_tokens_, authenticate_user
from main import app
import settings

# Python
from datetime import datetime, timedelta
from typing import Iterator, Callable, Any, Sequence
import re


test_database_manager: TestDatabaseManager | None = None


@pytest.fixture(scope='session', autouse=True)
def database_setup() -> Iterator[None]:
    global test_database_manager

    test_database_manager = TestDatabaseManager()
    #  test_database_manager.engine.echo = True

    settings.SECRET_KEY = 'test_secret'
    settings.JWT_ALGORITHM = 'HS256'

    run_all_migrations(test_database_manager.engine, echo=False)

    yield

    test_database_manager.dispose()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as client:
        return client


@pytest.fixture
def db() -> Iterator[DBConnection]:
    if not test_database_manager:
        raise Exception('Test database not initialized.')

    with test_database_manager.connect() as conn:
        def get_db() -> Iterator[DBConnection]:
            yield conn

        app.dependency_overrides[get_db_connection] = get_db

        yield conn

        conn.rollback()


@dataclass
class TestUser:
    id: int
    username: str
    password: str
    password_hash: str

    __test__ = False


@pytest.fixture
def user(db: DBConnection) -> TestUser:
    username = 'ValidUsername'
    password = 'ValidPassword1'
    password_hash = md5_crypt.hash(password)

    row = db.fetch_one(
        'INSERT INTO users (username, password_hash) '
        'VALUES (:username, :password_hash) '
        'RETURNING id;',
        {'username': username, 'password_hash': password_hash}
    )

    assert row is not None

    return TestUser(
        id=row.id,
        username=username,
        password=password,
        password_hash=password_hash
    )


@pytest.fixture
def users(db: DBConnection) -> tuple[TestUser, TestUser, TestUser]:
    username = 'ValidUsername'
    password = 'ValidPassword1'
    password_hash = md5_crypt.hash(password)

    users: list[TestUser] = []

    for i in range(3):
        row = db.fetch_one(
            'INSERT INTO users (username, password_hash) '
            'VALUES (:username, :password_hash) '
            'RETURNING id, username;',
            {'username': f'{username}_{i}', 'password_hash': password_hash}
        )
        assert row is not None

        users.append(
            TestUser(
                id=row.id,
                username=row.username,
                password=password,
                password_hash=password_hash
            )
        )

    return users[0], users[1], users[2]


@pytest.fixture
def fake_tokens(user: TestUser) -> Tokens:
    fake_access_token = jwt.encode(
        {
            'type': 'access',
            'sub': user.id,
            'exp': (datetime.utcnow() + timedelta(weeks=999)).timestamp(),
        },
        key='fake_secret',
        algorithm=settings.JWT_ALGORITHM
    )

    fake_refresh_token = jwt.encode(
        {
            'type': 'refresh',
            'sub': user.id,
            'exp': (datetime.utcnow() + timedelta(weeks=999)).timestamp(),
            'token_id': 69,
            'family_id': 420,
            'device_id': 33
        },
        key='fake_secret',
        algorithm=settings.JWT_ALGORITHM
    )

    return Tokens(access_token=fake_access_token, refresh_token=fake_refresh_token, device_id=69)


@contextmanager
def authenticate_requests(user: TestUser) -> Iterator[None]:
    try:
        app.dependency_overrides[authenticate_user] = lambda: user.id
        yield

    finally:
        app.dependency_overrides[authenticate_user] = authenticate_user


def assert_is_endpoint_authenticated(
    db: DBConnection,
    user: TestUser,
    client_method: Callable[..., Response],
    url: str,
    **client_kwargs: Any
):
    res = client_method(url)
    assert res.status_code in (401, 403)

    tokens, _ = generate_tokens_(db, user.id)
    assert tokens is not None

    if 'headers' in client_kwargs:
        client_kwargs['headers'].update({'Authorization': f'Bearer {tokens.access_token}'})
    else:
        client_kwargs['headers'] = {'Authorization': f'Bearer {tokens.access_token}'}

    res = client_method(url, **client_kwargs)
    assert res.status_code not in (401, 403)


def snake2camel(obj: dict[str, Any]) -> dict[str, Any]:
    camel2snake_pattern = re.compile(r'_([a-zA-Z0-9])')

    for key in obj.copy():
        snake_key = camel2snake_pattern.sub(lambda m: m.group(1).upper(), key)

        if snake_key == key:
            continue

        obj[snake_key] = obj[key]
        del obj[key]

    return obj


def model2camel(obj: BaseModel | Sequence[BaseModel]) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(obj, Sequence):
        return [snake2camel(obj_.model_dump()) for obj_ in obj]

    return snake2camel(obj.model_dump())
