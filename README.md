# Minesweeper-API

This API extends the functionality of the [Minesweeper client](https://github.com/MarcosTypeAP/Minesweeper-Client/tree/main), providing additional features such as saving unfinished games, time records, and customized settings so you can sync them across multiple devices.

# Documentation

The [documentation](https://minesweeper-api-production.up.railway.app/docs) is interactive and is automatically generated with Swagger from the source code, so it's always up-to-date.

# Instalation

### Download repo

Clone the repo.

```bash
git clone git@github.com:MarcosTypeAP/Minesweeper-API.git
cd Minesweeper-API
```

You need to set the environment variables found in `./env_vars` to a `.env` file.

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
| FASTAPI_DEBUG | Used for CORS and debug level logging | `0` | `1` |
| FASTAPI_HOST | If not set, it tries to use the container IP, otherwise, it defaults to `0.0.0.0` | Container IP or `0.0.0.0` | `127.0.0.1` |
| FASTAPI_PORT | This is overwritten by `$PORT` if it is set, usualy set by the docker host | `$PORT` or `4000` | `4000` |
| RUN_TESTS | Whether to run the entire test suite at startup | `0` | `1` |
| DATABASE_URL | Used to create the database engine | `sqlite+pysqlite:///:memory:` | `sqlite+pysqlite:///db/dev.db` |
| DATABASE_CHECK_TABLE | The API will check that the specified table exists on startup or stop the process if it does not || `users` |
