from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncIterator
from contextlib import asynccontextmanager
from database import database_manager
import routers
import settings


tags_metadata = [
    {
        'name': 'Authentication',
        'description': 'This endpoints provide secure access management, supporting token generation, rotation for enhanced security, and families for organized session control.'
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield

    if database_manager:
        database_manager.dispose()


app = FastAPI(lifespan=lifespan, openapi_tags=tags_metadata)

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
