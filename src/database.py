from fastapi import Depends
from sqlalchemy import create_engine, text, Row, Connection, Engine, StaticPool
from sqlalchemy.exc import ResourceClosedError, DatabaseError
from typing import Any, Sequence, Mapping, Annotated, Iterator
from contextlib import contextmanager
from utils import print_exception
from datetime import datetime, timedelta
import settings
import signal
import os


QueryParameter = Mapping[str, Any]


TIME_BETWEEN_CONNECTION_CHECKS = timedelta(minutes=5).total_seconds()


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


class DatabaseManager():
    connection_class = DBConnection
    last_connection_check_time = 0.0

    def __new__(cls) -> 'DatabaseManager':
        if not hasattr(cls, 'engine'):
            if settings.DATABASE_ENGINE == 'sqlite':
                if settings.DATABASE_LOCAL:
                    cls.engine = create_engine('sqlite+pysqlite:///db/db.dev.sql', connect_args={"check_same_thread": False})
                else:
                    cls.engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

            elif settings.DATABASE_ENGINE == 'postgresql':
                cls.engine = create_engine(settings.DATABASE_URL)

            else:
                raise Exception(f'Database engine not supported: DATABASE_ENGINE={settings.DATABASE_ENGINE}')

        cls.test_database()

        return super().__new__(cls)

    @classmethod
    def test_database(cls) -> None:
        if not cls.engine:
            raise Exception('Database not initialized.')

        if not settings.DATABASE_CHECK_TABLE:
            return

        with cls.engine.connect() as conn:
            try:
                conn.execute(text(f'SELECT 1 FROM {settings.DATABASE_CHECK_TABLE};'))

            except Exception as exception:
                print_exception(exception)
                conn.rollback()
                cls.engine.dispose()
                os.kill(os.getppid(), signal.SIGTERM)  # Aim uvicorn process

    @classmethod
    def _check_engine_connection(cls) -> None:
        if not cls.engine:
            raise Exception('Database not initialized.')

        try:
            with cls.engine.connect() as conn:
                conn.execute(text('SELECT 1;'))

        except DatabaseError as exception:
            print('DatabaseError when checking connection. Recreating engine.')

            if settings.DEBUG:
                print_exception(exception)

            del cls.engine
            cls.__new__(cls)

    def dispose(self, close: bool = True) -> None:
        if not self.engine:
            raise Exception('Database not initialized.')

        self.engine.dispose(close)

    @contextmanager
    def connect(self) -> Iterator[DBConnection]:
        if not self.engine:
            raise Exception('Database not initialized.')

        now = datetime.utcnow().timestamp()

        if self.last_connection_check_time + TIME_BETWEEN_CONNECTION_CHECKS < now:
            self._check_engine_connection()
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
