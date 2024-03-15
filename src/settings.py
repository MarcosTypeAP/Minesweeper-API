import os
import dotenv
from typing import Type, TypeVar, Any


dotenv.load_dotenv('.env')


T = TypeVar('T', str, int, bool)


def getvar(type_: Type[T], key: str, default: T | None = None) -> T:
    value: Any = os.environ.get(key, default=default)

    if value is None:
        raise KeyError(f"Environment variable ${key} not set.")

    if type_ is bool:
        value = int(value)

    return type_(value)


APP_DIR = os.path.abspath('.')

DEBUG: bool = getvar(bool, 'FASTAPI_DEBUG', default=False)

CLIENT_URL = getvar(str, 'CLIENT_URL', default='')
CLIENT_DEBUG_URL = getvar(str, 'CLIENT_DEBUG_URL', default='http://127.0.0.1:3000')

SECRET_KEY = getvar(str, 'SECRET_KEY')
JWT_ALGORITHM = getvar(str, 'JWT_ALGORITHM', default='HS256')

ACCESS_TOKEN_EXPIRE_MINUTES = getvar(int, 'ACCESS_TOKEN_EXPIRE_MINUTES', default=15)
REFRESH_TOKEN_EXPIRE_DAYS = getvar(int, 'REFRESH_TOKEN_EXPIRE_DAYS', default=30)

DATABASE_URL = getvar(str, 'DATABASE_URL', default='sqlite+pysqlite:///:memory:')
DATABASE_CHECK_TABLE = getvar(str, 'DATABASE_CHECK_TABLE', default='')
