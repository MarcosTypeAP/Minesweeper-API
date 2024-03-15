from sqlalchemy import text, Engine
import settings
import sys
import os
import re


MIGRATIONS_DIR = settings.APP_DIR + '/migrations'


def get_all_migration_ids() -> list[int]:
    if not os.path.exists(MIGRATIONS_DIR):
        print('There is no migrations directory.')
        return []

    migration_filenames = os.listdir(MIGRATIONS_DIR)

    if not migration_filenames:
        print('There is no migration files.')
        return []

    migration_ids = [
        int(id)
        for filename in migration_filenames
        if (id := filename.split('-')[0]).isnumeric()
    ]

    if not migration_ids:
        print('There is no valid migration files. They must start with its ID. Eg: 0-migration-name.sql')
        return []

    return migration_ids


def get_migration_ids() -> list[int]:
    if len(sys.argv) < 2:
        print('Missing args. Pass -h for help.')
        return []

    arg = sys.argv[1]

    if arg in ('--help', '-h'):
        print('Pass a single migration ID or a [start, end] range. Eg: 2-4 to select 2,3,4')
        print('Pass "last" to select the latest migration.')
        print('Pass "all" to select all migrations.')
        return []

    if arg == 'last':
        return [get_all_migration_ids()[-1]]

    if arg == 'all':
        return get_all_migration_ids()

    if arg.isnumeric():
        return [int(arg)]

    if '-' not in arg:
        print('Invalid arg. Pass -h for help.')
        return []

    start, end = arg.split('-', 1)

    if not start.isnumeric() or not end.isnumeric():
        print('The start and end of the range must be positive integers. Eg: 0-7')
        return []

    return list(range(int(start), int(end) + 1))


def parse_sql_file(file: str) -> list[str]:
    comment_pattern = re.compile(r'^ *--')

    statements: list[str] = []

    with open(file, 'r') as fp:
        for query in fp.read().split(';'):
            statement = ''

            for line in query:
                if comment_pattern.match(line):
                    continue

                statement += line

            statements.append(statement)

    return statements


def run_all_migrations(engine: Engine, echo: bool = True) -> None:
    migration_ids = get_all_migration_ids()

    if not migration_ids:
        return

    run_migrations(migration_ids, engine, echo)


def run_migrations(migration_ids: list[int], engine: Engine, echo: bool = True) -> None:
    if not os.path.exists(MIGRATIONS_DIR):
        print('There is no migrations directory.')
        return

    ids = {str(id) for id in migration_ids}

    migration_files: list[tuple[int, str]] = [
        (int(file_id), MIGRATIONS_DIR + '/' + filename)
        for filename in os.listdir(MIGRATIONS_DIR)
        if (file_id := filename.split('-', 1)[0]) in ids
    ]

    if not migration_files:
        print('There is no migrations with this ids:', migration_ids)
        return

    if len(migration_files) != len(ids):
        diff = ids.difference({str(file[0]) for file in migration_files})
        print('There is no migrations with this ids:', sorted([int(id) for id in diff]))
        return

    migration_files.sort(key=lambda file: file[0])

    init_echo = engine.echo

    try:
        engine.echo = echo

        for file in migration_files:
            sql_statements = parse_sql_file(file[1])

            print(f'Applying migration {file[0]}.')

            with engine.begin() as conn:
                for statement in sql_statements:
                    conn.execute(text(statement))

    finally:
        engine.echo = init_echo  # type: ignore

    return


def run() -> None:
    ids = get_migration_ids()

    if not ids:
        return

    settings.DATABASE_CHECK_TABLE = ''

    from database import get_db_engine
    engine = get_db_engine()

    run_migrations(ids, engine)


if __name__ == '__main__':
    run()
