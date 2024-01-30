from fastapi import APIRouter, HTTPException, status, Body, Response
from pydantic import Field
from database import DBConnectionDep, DBConnection
from typing import Annotated, Literal
from models import FromDBModel, CamelModel
from .auth import AuthenticatedUserID
from utils import get_json_error_resonse


class GameSettings(FromDBModel, CamelModel):
    theme: Annotated[int, Field(description='Theme ID.')]
    initial_zoom: bool
    action_toggle: bool
    default_action: Literal['dig', 'mark']
    long_tap_delay: Annotated[int, Field(ge=0, description='Time in milliseconds.')]
    easy_digging: bool
    vibration: bool
    vibration_intensity: Annotated[int, Field(ge=0, description='Time in milliseconds.')]
    modified_at: int


def save_game_settings(db: DBConnection, user_id: int, game_settings: GameSettings) -> None:
    db.execute(
        'INSERT INTO game_settings ('
        '    user_id, theme, initial_zoom, action_toggle, default_action, '
        '    long_tap_delay, easy_digging, vibration, vibration_intensity, modified_at'
        ') '
        'VALUES ('
        '    :user_id, :theme, :initial_zoom, :action_toggle, :default_action, '
        '    :long_tap_delay, :easy_digging, :vibration, :vibration_intensity, :modified_at'
        ');',
        {**game_settings.model_dump(), 'user_id': user_id},
    )


def update_game_settings(db: DBConnection, game_settings_id: int, game_settings: GameSettings) -> None:
    db.execute(
        'UPDATE game_settings '
        'SET modified_at = :modified_at, theme = :theme, initial_zoom = :initial_zoom, '
        '    action_toggle = :action_toggle, default_action = :default_action, '
        '    long_tap_delay = :long_tap_delay, easy_digging = :easy_digging, '
        '    vibration = :vibration, vibration_intensity = :vibration_intensity '
        'WHERE id = :game_settings_id;',
        {**game_settings.model_dump(), 'game_settings_id': game_settings_id},
    )


def get_game_settings_(db: DBConnection, user_id: int) -> GameSettings | None:
    row = db.fetch_one(
        'SELECT * '
        'FROM game_settings '
        'WHERE user_id = :user_id;',
        {'user_id': user_id}
    )

    if row is None:
        return None

    return GameSettings.model_validate(row)


not_found_exception = HTTPException(status_code=status.HTTP_404_NOT_FOUND)
there_is_newer_version_exception = HTTPException(status_code=status.HTTP_409_CONFLICT, detail='There is a newer version.')

router = APIRouter(tags=['Game Settings'])


@router.put('/', response_model=GameSettings, responses={status.HTTP_409_CONFLICT: get_json_error_resonse('Already a Newer Version')})
def save_settings(user_id: AuthenticatedUserID, game_settings: Annotated[GameSettings, Body()], response: Response, db: DBConnectionDep) -> GameSettings:
    '''
    Save or update the settings if the provided data has been modified more recently than the existing record.
    Otherwise, it will result in an error (409).
    '''
    row = db.fetch_one(
        'SELECT id, modified_at '
        'FROM game_settings '
        'WHERE user_id = :user_id;',
        {'user_id': user_id}
    )

    if row is None:
        response.status_code = status.HTTP_201_CREATED
        save_game_settings(db, user_id, game_settings)
        return game_settings

    game_settings_id = row.id
    modified_at = row.modified_at

    if modified_at > game_settings.modified_at:
        raise there_is_newer_version_exception

    update_game_settings(db, game_settings_id, game_settings)

    return game_settings


@router.get('/', response_model=GameSettings, responses={status.HTTP_404_NOT_FOUND: get_json_error_resonse()})
def get_game_settings(user_id: AuthenticatedUserID, db: DBConnectionDep) -> GameSettings:
    game_settings = get_game_settings_(db, user_id)

    if game_settings is None:
        raise not_found_exception

    return game_settings
