from sqlalchemy import text, Engine
from database import get_db_engine
import settings
import sys
import os
import re
from typing import Literal


MIGRATIONS_DIR = settings.APP_DIR + '/migrations'


def get_migration_ids() -> list[int] | None:
    if len(sys.argv) < 2:
        print('Missing migration ID.')
        return None

    if sys.argv[1] in ('--help', '-h'):
        print('Pass a migration ID or "last" to select the latest migration.')
        return None

    if not os.path.exists(MIGRATIONS_DIR):
        print('There is no migrations directory.')
        return None

    migration_filenames = os.listdir(MIGRATIONS_DIR)

    if not migration_filenames:
        print('There is no migration files.')
        return None

    if sys.argv[1] in ('last', 'all'):
        migration_ids = [
            int(first_digit)
            for filename in migration_filenames
            if filename and (first_digit := filename[0]).isnumeric()
        ]

        if not migration_ids:
            print('There is no valid migration files. They must start with its ID. Eg: 0-migration-name.sql')
            return None

        if sys.argv[1] == 'all':
            return migration_ids

        return [max(migration_ids)]

    if not sys.argv[1].isnumeric():
        print('Migration ID must be a positive integer.')
        return None

    return [int(sys.argv[1])]


def parse_sql_file(file: str, engine: Literal['sqlite', 'postgresql']) -> list[str]:
    statements: list[str] = []

    comment_line_pattern = re.compile(r'^ *--')

    with open(file, 'r') as fp:
        for sql_statement in fp.read().split(';'):
            statement_lines: list[str] = []

            for line in sql_statement.splitlines():
                if comment_line_pattern.match(line):
                    continue

                if '--' in line:
                    statement_part, comment = line.rsplit('--', 1)

                    if engine == 'sqlite' and 'postgresql' in comment:
                        continue

                    if engine == 'postgresql' and 'sqlite' in comment:
                        continue

                    statement_lines.append(statement_part)
                    continue

                statement_lines.append(line)

            if statement_lines:
                if len(statement_lines) == 1 and statement_lines[0] == '':
                    continue

                statements.append('\n'.join(statement_lines) + ';')

    return statements


def run_all_migrations(engine: Engine, echo: bool = True) -> None:
    migration_filenames = os.listdir(MIGRATIONS_DIR)

    if not migration_filenames:
        print('There is no migration files.')
        return None

    migration_ids = [
        int(first_digit)
        for filename in migration_filenames
        if filename and (first_digit := filename[0]).isnumeric()
    ]

    if not migration_ids:
        print('There is no valid migration files. They must start with its ID. Eg: 0-migration-name.sql')
        return

    run_migrations(migration_ids, engine, echo)


def run_migrations(migration_ids: list[int], engine: Engine, echo: bool = True) -> None:
    migration_filenames = os.listdir(MIGRATIONS_DIR)

    init_echo = engine.echo

    try:
        engine.echo = echo

        for migration_id in migration_ids:
            migration_path: str | None = None

            for filename in migration_filenames:
                if filename.startswith(str(migration_id)):
                    migration_path = MIGRATIONS_DIR + '/' + filename
                    break

            if migration_path is None:
                return

            sql_statements = parse_sql_file(migration_path, settings.DATABASE_ENGINE)

            print(f'Applying migration {migration_id}.')

            with engine.begin() as conn:
                for statement in sql_statements:
                    conn.execute(text(statement))
    finally:
        engine.echo = init_echo  # type: ignore


def run() -> None:
    ids = get_migration_ids()

    if ids is None:
        return

    engine = get_db_engine()

    run_migrations(ids, engine)


if __name__ == '__main__':
    run()
