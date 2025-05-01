from types import MethodType
from fastapi import Depends
from libsql_client.config import urllib  # type: ignore[reportMissingTypeStubs]
from sqlalchemy import create_engine, text, Row, Connection, Engine, StaticPool
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ResourceClosedError, DatabaseError
import libsql_client as libsql  # type: ignore[reportMissingTypeStubs]
import libsql_client.http as libsql_http  # type: ignore[reportMissingTypeStubs]
from pydantic.alias_generators import to_snake
from typing import Any, List, Sequence, Mapping, Annotated, Iterator, cast
from contextlib import contextmanager
from migrate import run_all_migrations
from utils import print_exception
from datetime import datetime, timedelta
import settings
import signal
import time
import os


QueryParameter = Mapping[str, Any]


TIME_BETWEEN_CONNECTION_CHECKS = timedelta(minutes=5)


def fix_turso_server_false_positives(client: libsql.ClientSync) -> None:
    http_client = cast(libsql_http.HttpClient, client._client)  # type: ignore[reportPrivateUsage]

    async def fixed_send(self: libsql_http.HttpClient, method: str, path: str, request_body: Any) -> Any:
        url = urllib.parse.urljoin(self._url, path)  # type: ignore[reportPrivateUsage]
        async with self._session.request(method, url, json=request_body) as resp:  # type: ignore[reportPrivateUsage]
            if not resp.ok:
                if resp.content_type == "application/json":
                    resp_json = await resp.json()
                    if "message" in resp_json:
                        message = resp_json["message"]
                        code = resp_json.get("code") or "UNKNOWN"
                        raise libsql.LibsqlError(message, code)
                elif resp.content_type == "text/plain":
                    resp_text = await resp.text()
                    raise libsql.LibsqlError(
                        "Server returned HTTP status "
                        f"{resp.status} and error: {resp_text!r}",
                        "SERVER_ERROR",
                    )
                raise libsql.LibsqlError(
                    f"Server returned HTTP status {resp.status}",
                    "SERVER_ERROR",
                )

            resp_json = await resp.json()

            if set(resp_json.keys()) == {'message', 'code'}:  # Error response
                message = resp_json["message"]
                code = resp_json.get("code") or "UNKNOWN"
                raise libsql.LibsqlError(message, code)

            return resp_json

    http_client._send = MethodType(fixed_send, http_client)  # type: ignore[reportPrivateUsage]


class TmpRow():
    def __init__(self, row: libsql.Row) -> None:
        self._row = row

    def __getitem__(self, key: str) -> Any:
        try:
            return self._row[key]
        except KeyError:
            return self._row[to_snake(key)]

    def __getattr__(self, attr: str) -> Any:
        return self[attr]


Params = dict[str, libsql.InValue] | None


class DBConnection:
    # def __init__(self, connection: Connection):
    #     self.connection = connection
    def __init__(self, client: libsql.ClientSync):
        self.client = client

    def fetch_one(self, statement: str, parameters: Params = None) -> TmpRow | None:
        result = self.client.execute(libsql.Statement(statement, parameters))

        try:
            if not result.rows:
                return None
            return TmpRow(result.rows[0])
        except Exception:
            raise

    def fetch_many(self, statement: str, parameters: Params = None) -> Sequence[TmpRow]:
        result = self.client.execute(libsql.Statement(statement, parameters))

        try:
            return tuple((TmpRow(row) for row in result.rows))
        except ResourceClosedError:
            return []

    def execute(self, statement: str, parameters: Params | Sequence[Params] = None) -> None:
        if isinstance(parameters, Sequence):
            if len(parameters) == 0:
                return
            self.client.batch([(statement, params) for params in parameters])
        else:
            self.client.execute(libsql.Statement(statement, parameters))

    def commit(self) -> None:
        # self.connection.commit()
        pass

    def rollback(self) -> None:
        # self.connection.rollback()
        pass


class DatabaseManager:
    connection_class = DBConnection
    last_connection_check_time = datetime.fromtimestamp(0)
    connection_check_retries = 5
    engine: Engine | None = None

    def __new__(cls) -> 'DatabaseManager':
        return super().__new__(cls)

        if cls.engine is None:
            cls.engine = cls._create_engine()

            if cls.engine is None:
                cls._dispose_and_end_process()
            else:
                cls._test_database()

        return super().__new__(cls)

    @classmethod
    def _create_engine(cls) -> Engine | None:
        url_parts = make_url(settings.DATABASE_URL)
        is_tmp_db = (
            (not url_parts.database and not url_parts.host) or
            (':memory:' in (url_parts.database or '')) or
            (url_parts.query.get('mode') == 'memory')
        )

        if not is_tmp_db and not url_parts.host and url_parts.database is not None:
            if not os.path.isfile(url_parts.database):
                print(f'Error: {url_parts.database} does not exist.')
                return None

        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool if is_tmp_db else None
        )

        if is_tmp_db:
            print('Using temporary database. Running migrations.')
            run_all_migrations(engine, echo=False)

        return engine

    @classmethod
    def _test_database(cls) -> None:
        if cls.engine is None:
            raise Exception('Database not initialized.')

        success = cls._check_engine_connection()

        if not success:
            cls._dispose_and_end_process()
            return

        if not settings.DATABASE_CHECK_TABLE:
            return

        try:
            with cls.engine.connect() as conn:
                conn.execute(text(f'SELECT 1 FROM {settings.DATABASE_CHECK_TABLE};'))

        except Exception as exception:
            print(f'Error: Table `{settings.DATABASE_CHECK_TABLE}` does not exist in the database.')

            if settings.DEBUG:
                print_exception(exception)

            cls._dispose_and_end_process()

    @classmethod
    def _check_engine_connection(cls) -> bool:
        if cls.engine is None:
            raise Exception('Database not initialized.')

        if cls.connection_check_retries <= 0:
            print('Error: The maximum number of attempts was reached verifying the database connection.')
            return False

        try:
            with cls.engine.connect() as conn:
                conn.execute(text('SELECT 1;'))

        except DatabaseError as exception:
            print('DatabaseError when checking connection. Recreating engine.')

            if settings.DEBUG:
                print_exception(exception)

            time.sleep(0.5)
            cls.connection_check_retries -= 1
            cls.engine.dispose()
            cls.engine = cls._create_engine()
            return cls._check_engine_connection()

        return True

    @classmethod
    def _dispose_and_end_process(cls) -> None:
        if cls.engine is not None:
            cls.engine.dispose()

        os.kill(os.getppid(), signal.SIGTERM)  # Aim uvicorn process
        os.kill(os.getpid(), signal.SIGTERM)

    def dispose(self, close: bool = True) -> None:
        if not self.engine:
            raise Exception('Database not initialized.')

        self.engine.dispose(close)

    @contextmanager
    def connect(self) -> Iterator[DBConnection]:
        url = make_url(settings.DATABASE_URL)

        auth_token = url.normalized_query.get('authToken')
        if auth_token is None:
            raise Exception("Missing database auth token")
        auth_token = auth_token[0]

        with libsql.create_client_sync(f'https://{url.host}', auth_token=auth_token, tls=True) as client:
            fix_turso_server_false_positives(client)
            yield DBConnection(client)
        return

        if not self.engine:
            raise Exception('Database not initialized.')

        now = datetime.now()

        if now > self.last_connection_check_time + TIME_BETWEEN_CONNECTION_CHECKS:
            success = self._check_engine_connection()

            if not success:
                self._dispose_and_end_process()
                return

            self.last_connection_check_time = now

        with self.engine.begin() as conn:
            yield self.connection_class(conn)


#  class TestDBConnection(DBConnection):
    #  def commit(self, force: bool = False) -> None:
        #  if force:
            #  self.connection.commit()


class TestDatabaseManager(DatabaseManager):
    #  connection_class = TestDBConnection
    is_initialized = False

    def __new__(cls) -> 'TestDatabaseManager':
        if not cls.is_initialized:
            cls.engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={"check_same_thread": False}, poolclass=StaticPool)
            cls.is_initialized = True

        return super(DatabaseManager, cls).__new__(cls)


database_manager: DatabaseManager = DatabaseManager()


def get_db_connection():
    with database_manager.connect() as conn:
        yield conn


def get_db_engine() -> Engine | None:
    return database_manager.engine


DBConnectionDep = Annotated[DBConnection, Depends(get_db_connection)]
