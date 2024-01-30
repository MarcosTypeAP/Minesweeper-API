from fastapi import Depends
from sqlalchemy import create_engine, text, Row, Connection, Engine, StaticPool
from sqlalchemy.exc import ResourceClosedError
from typing import Any, Sequence, Mapping, Annotated, Iterator
from contextlib import contextmanager
import settings


QueryParameter = Mapping[str, Any]


class DBConnection:
    def __init__(self, connection: Connection):
        self.connection = connection

    def fetch_one(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> Row[Any] | None:
        result = self.connection.execute(text(statement), parameters)

        try:
            row = result.first()
        except ResourceClosedError:
            return None

        if not row:
            return None

        return row

    def fetch_many(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> Sequence[Row[Any]] | None:
        result = self.connection.execute(text(statement), parameters)

        try:
            row = result.all()
        except ResourceClosedError:
            return None

        if not row:
            return None

        return row

    def execute(self, statement: str, parameters: QueryParameter | Sequence[QueryParameter] | None = None) -> None:
        self.connection.execute(text(statement), parameters)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()


class DatabaseManager():
    connection_class = DBConnection

    def __new__(cls) -> 'DatabaseManager':
        if not hasattr(cls, 'engine'):
            if settings.DATABASE_ENGINE == 'sqlite':
                if settings.DEBUG:
                    cls.engine = create_engine('sqlite+pysqlite:///db/db.dev.sql', connect_args={"check_same_thread": False})
                else:
                    cls.engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

            elif settings.DATABASE_ENGINE == 'postgresql':
                cls.engine = create_engine(settings.DATABASE_URL)

            else:
                raise Exception(f'Database engine not supported: DATABASE_ENGINE={settings.DATABASE_ENGINE}')

        return super().__new__(cls)

    def dispose(self, close: bool = True) -> None:
        if not self.engine:
            raise Exception('Database not initialized.')

        self.engine.dispose(close)

    @contextmanager
    def connect(self) -> Iterator[DBConnection]:
        if not self.engine:
            raise Exception('Database not initialized.')

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
