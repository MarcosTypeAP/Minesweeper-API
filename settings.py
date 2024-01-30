import os
import dotenv
from typing import Type, TypeVar, Literal, Any


dotenv.load_dotenv('.env')


T = TypeVar('T', str, int, bool)


def getvar(type_: Type[T], key: str, default: T | None = None) -> T:
    value: Any = os.environ.get(key, default=default)

    if value is None:
        raise KeyError(f"Environment variable '{key}' does not exist.")

    if type_ is bool:
        value = int(value)

    return type_(value)


APP_DIR = os.path.abspath('.')

DEBUG: bool = getvar(bool, 'FASTAPI_DEBUG', default=False)

HOST = getvar(str, 'FASTAPI_HOST', default='0.0.0.0')
PORT = getvar(int, 'FASTAPI_PORT', default=4000)

CLIENT_HOST = getvar(str, 'CLIENT_HOST', default='127.0.0.1')
CLIENT_PORT = getvar(int, 'CLIENT_PORT', default=3000)
CLIENT_HTTPS = getvar(bool, 'CLIENT_HTTPS', default=True)

STATIC_URL = '/static'
STATIC_DIR = os.path.join(APP_DIR, '/static')

SECRET_KEY = getvar(str, 'SECRET_KEY')
JWT_ALGORITHM = getvar(str, 'JWT_ALGORITHM', default='HS256')

ACCESS_TOKEN_EXPIRE_MINUTES = getvar(int, 'ACCESS_TOKEN_EXPIRE_MINUTES', default=15)
REFRESH_TOKEN_EXPIRE_DAYS = getvar(int, 'REFRESH_TOKEN_EXPIRE_DAYS', default=30)


def get_engine_name() -> Literal['sqlite', 'postgresql']:
    value = getvar(str, 'DATABASE_ENGINE')

    if value == 'sqlite':
        return 'sqlite'

    if value == 'postgresql':
        return 'postgresql'

    raise Exception(f'Database engine not supported: DATABASE_ENGINE={value}')


DATABASE_ENGINE = get_engine_name()
DATABASE_URL = getvar(str, 'DATABASE_URL')
