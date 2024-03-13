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

You need to set the following environment variables to a `.env` file.

| Name | Info | Required | Example |
|---|---|---|---|
| SECRET_KEY | Random string that can be generated with `openssl rand -hex 32` | True | `da054f293d492d` |
| JWT_ALGORITHM | Must be one of [these](https://python-jose.readthedocs.io/en/latest/jws) | True | `HS256` |
| ACCESS_TOKEN_EXPIRE_MINUTES | Lifetime of the access token in minutes | True | `15` |
| REFRESH_TOKEN_EXPIRE_DAYS | Lifetime of the refresh token in days | True | `30` |
| CLIENT_URL | Used for CORS | False | `https://example.client` |
| CLIENT_DEBUG_URL | Used for CORS | False | `http://localhost:3000` |
| FASTAPI_DEBUG | Used for CORS and debug level logging | False | `0` |
| RUN_TESTS | Whether to run the entire test suite at startup | False | `1` |
| DATABASE_ENGINE | The used engine. Must be `sqlite` or `postgresql` | True | `sqlite` |
| DATABASE_URL | Used to create the database engine | True | `sqlite+pysqlite:///:memory:` |
| DATABASE_LOCAL | Whether use a local database | False | `0` |
| DATABASE_CHECK_TABLE | The API will check that the specified table exists on startup or shutdown if it does not | False | `users` |



