from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncIterator
from contextlib import asynccontextmanager
from database import database_manager
import routers
import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield

    if database_manager:
        database_manager.dispose()


tags_metadata = [
    {
        'name': 'Authentication',
        'description': (
            'This endpoints provide secure access management, '
            'supporting token generation, rotation for enhanced security, '
            'and families for organized session control.'
        )
    }
]

description = (
    'This API extends the functionality of the [Minesweeper client]'
    '(https://github.com/MarcosTypeAP/Minesweeper-Client/tree/main), '
    'providing additional features such as saving unfinished games, '
    'time records, and customized settings so you can sync them across '
    'multiple devices.'
)

app = FastAPI(
    title='Minesweeper API',
    description=description,
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

app.include_router(routers.auth, prefix='/api/auth')
app.include_router(routers.users, prefix='/api/users')
app.include_router(routers.games, prefix='/api/games')
app.include_router(routers.times, prefix='/api/timerecords')
app.include_router(routers.game_settings, prefix='/api/settings')

origins: list[str] = []

if settings.CLIENT_URL:
    origins.append(settings.CLIENT_URL)

if settings.DEBUG:
    origins += [
        settings.CLIENT_DEBUG_URL,
        'http://127.0.0.1:3000',
        'http://localhost:3000',
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)


@app.get('/api/healthcheck', tags=['Health Check'], status_code=status.HTTP_200_OK)
def health_check() -> None:
    '''
    Endpoint just for monitoring.
    Always returns 200 OK.
    '''
    return
