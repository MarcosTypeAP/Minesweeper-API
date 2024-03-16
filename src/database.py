from fastapi import Depends
from sqlalchemy import create_engine, text, Row, Connection, Engine, StaticPool
from sqlalchemy.exc import ResourceClosedError, DatabaseError
from typing import Any, Sequence, Mapping, Annotated, Iterator
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


class DBConnection:
    def __init__(self, connection: Connection):
        self.connection = connection

    def fetch_one(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> Row[Any] | None:
        result = self.connection.execute(text(statement), parameters)

        try:
            return result.first()
        except ResourceClosedError:
            return None

    def fetch_many(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> Sequence[Row[Any]]:
        result = self.connection.execute(text(statement), parameters)

        try:
            return result.all()
        except ResourceClosedError:
            return []

    def execute(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> None:
        self.connection.execute(text(statement), parameters)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()


class DatabaseManager:
    connection_class = DBConnection
    last_connection_check_time = datetime.fromtimestamp(0)
    connection_check_retries = 5

    def __new__(cls) -> 'DatabaseManager':
        if not hasattr(cls, 'engine'):
            cls.engine = cls._create_engine()

        cls._test_database()

        return super().__new__(cls)

    @classmethod
    def _create_engine(cls) -> Engine:
        url_parts = settings.DATABASE_URL.split('://', 1)[1].split('?', 1)
        url = url_parts[0]
        params = ''

        if len(url_parts) == 2:
            params = url_parts[1]

        is_tmp_db = url in ('/', '') or ':memory:' in url or 'mode=memory' in params

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
        if not cls.engine:
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
        if not cls.engine:
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
        cls.engine.dispose()
        os.kill(os.getppid(), signal.SIGTERM)  # Aim uvicorn process
        os.kill(os.getpid(), signal.SIGTERM)

    def dispose(self, close: bool = True) -> None:
        if not self.engine:
            raise Exception('Database not initialized.')

        self.engine.dispose(close)

    @contextmanager
    def connect(self) -> Iterator[DBConnection]:
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


def get_db_engine() -> Engine:
    return database_manager.engine


DBConnectionDep = Annotated[DBConnection, Depends(get_db_connection)]
