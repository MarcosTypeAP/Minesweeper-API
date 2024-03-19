# Minesweeper-API

This API extends the functionality of the [Minesweeper client](https://github.com/MarcosTypeAP/Minesweeper-Client/tree/main), providing additional features such as saving unfinished games, time records, and customized settings so you can sync them across multiple devices.

# Documentation

The [documentation](https://minesweeper-api-production.up.railway.app/docs) is interactive and is automatically generated with Swagger from the source code, so it's always up-to-date.

# Installation

<details>

<summary>Quick Installation</summary>

```bash
git clone git@github.com:MarcosTypeAP/Minesweeper-API.git
cd Minesweeper-API
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env

# If you want to use a file as the database
echo "DATABASE_URL=sqlite+pysqlite:///db/dev.db" >> .env
docker-compose run --rm api bash -c "touch db/dev.db && python3 src/migrate.py all"

docker-compose up
```

Now you can test it going to http://localhost:4000/docs

</details>

Clone the repo.

```bash
git clone git@github.com:MarcosTypeAP/Minesweeper-API.git
cd Minesweeper-API
```

You need to set the required environment variables to a `.env` file:

```bash
echo SECRET_KEY=$(openssl rand -hex 32) >> .env
```

These are all the variables that can be configured:

#### Required:

| Name | Info | Default | Example |
|---|---|---|---|
| SECRET_KEY | Random string that can be generated with `openssl rand -hex 32` || `da054f293d492d` |

#### Optional:

| Name | Info | Default | Example |
|---|---|---|---|
| JWT_ALGORITHM | Must be one of [these](https://python-jose.readthedocs.io/en/latest/jws) | `HS256` | `HS256` |
| ACCESS_TOKEN_EXPIRE_MINUTES | Lifetime of the access token in minutes | `15` | `10` |
| REFRESH_TOKEN_EXPIRE_DAYS | Lifetime of the refresh token in days | `30` | `15` |
| CLIENT_URL | Used for CORS || `https://example.client` |
| CLIENT_DEBUG_URL | Used for CORS | `http://127.0.0.1:3000` | `http://localhost:3000` |
| FASTAPI_DEBUG | Used for CORS, log level, auto-reload, etc | `0` | `1` |
| FASTAPI_HOST | If not set, it tries to use the container IP, otherwise, it defaults to `0.0.0.0` | Container IP or `0.0.0.0` | `127.0.0.1` |
| FASTAPI_PORT | This is overwritten by `$PORT` if it is set, usualy set by the docker host | `$PORT` or `4000` | `4000` |
| RUN_TESTS | Whether to run the entire test suite at startup | `0` | `1` |
| DATABASE_URL | Used to create the database engine | `sqlite+pysqlite:///:memory:` | `sqlite+pysqlite:///db/dev.db` |
| DATABASE_CHECK_TABLE | The API will check that the specified table exists on startup or stop the process if it does not || `users` |

### Build image

If you are not using `docker-compose`, you must build the image manually:

```bash
docker build --tag minesweeper-api .
```

### Local database

If you configured the `DATABASE_URL` variable to point to a local file database, first you have to create a `volume` and the database file.
In both cases, with a local or external database, you have to run the migrations:

With `docker-compose`:

```bash
docker-compose run --rm api bash -c "touch db/dev.db && python3 src/migrate.py all"
```

or only `docker`:

```bash
docker volume create minesweeper-api-db

docker run --rm --tty \
    --env-file .env \
    --mount type=volume,src=minesweeper-api-db,dst=/app/db \
    --user root:root \
    minesweeper-api bash -c "touch db/dev.db && chown -R nonroot:nonroot db"

docker run --rm --tty \
    --env-file .env \
    --mount type=volume,src=minesweeper-api-db,dst=/app/db \
    minesweeper-api python3 src/migrate.py all
```

### Run the API

#### Docker Compose

```bash
docker-compose up
```

#### Docker

```bash
docker run --rm --tty --interactive \
    --name minesweeper-api \
    --env-file .env \
    --mount type=volume,src=minesweeper-api-db,dst=/app/db \
    --publish 127.0.0.1:4000:4000 \
    minesweeper-api
```

Now you can test it going to http://localhost:4000/docs
