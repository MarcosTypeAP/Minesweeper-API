from fastapi import APIRouter, HTTPException, status, Body, Response
from database import DBConnectionDep, DBConnection
from typing import Annotated
from models import User, CamelModel
from .games import Game, save_games_, update_game, get_games_
from .times import TimeRecord, save_time_records_, get_time_records_
from .game_settings import GameSettings, update_game_settings, save_game_settings, get_game_settings_
from .auth import AuthenticatedUserID
from utils import get_json_error_resonse


class SyncData(CamelModel):
    games: list[Game]
    time_records: list[TimeRecord]
    settings: GameSettings


class OptionalSyncData(CamelModel):
    games: list[Game]
    time_records: list[TimeRecord]
    settings: GameSettings | None


def get_user_(db: DBConnection, user_id: int) -> User | None:
    row = db.fetch_one(
        'SELECT username '
        'FROM users '
        'WHERE id = :user_id;',
        {'user_id': user_id}
    )

    if row is None:
        return None

    return User.model_validate(row)


not_found_exception = HTTPException(status_code=status.HTTP_404_NOT_FOUND)

router = APIRouter(tags=['Users'])


@router.get('/me', response_model=User)
def get_user(user_id: AuthenticatedUserID, db: DBConnectionDep) -> User:
    '''
    Retrieve user data.
    '''
    user = get_user_(db, user_id)

    if user is None:
        raise not_found_exception

    return user


@router.put('/sync', response_model=OptionalSyncData, responses={
    status.HTTP_409_CONFLICT: get_json_error_resonse('Repeated Identifiers')
})
def sync_data(user_id: AuthenticatedUserID, sync_data: Annotated[SyncData, Body()], response: Response, db: DBConnectionDep) -> OptionalSyncData:
    '''
    Compare provided data with existing records, updating or saving based on creation or modification times.
    Providing games with duplicate 'difficulty' or records with repeated 'id' will result in an error (409).
    Retrieve the latest data.

    '''
    has_created = False

    if sync_data.time_records:
        rows = db.fetch_many(
            'SELECT id '
            'FROM time_records '
            'WHERE user_id = :user_id;',
            {'user_id': user_id}
        )

        if not rows:
            save_time_records_(db, user_id, sync_data.time_records)
            has_created = True

        else:
            time_record_ids = set((record.id for record in sync_data.time_records))

            if len(time_record_ids) < len(sync_data.time_records):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='There are TimeRecords with repeated IDs.')

            saved_time_record_ids = set((row.id for row in rows))

            time_record_ids_to_save = time_record_ids.difference(saved_time_record_ids)

            save_time_records_(db, user_id, list(filter(lambda record: record.id in time_record_ids_to_save, sync_data.time_records)))

            if time_record_ids_to_save:
                has_created = True

    row = db.fetch_one(
        'SELECT id, modified_at '
        'FROM game_settings '
        'WHERE user_id = :user_id;',
        {'user_id': user_id}
    )

    if row is None:
        save_game_settings(db, user_id, sync_data.settings)
        has_created = True

    elif sync_data.settings.modified_at > row.modified_at:
        update_game_settings(db, row.id, sync_data.settings)

    if sync_data.games:
        rows = db.fetch_many(
            'SELECT id, difficulty, created_at '
            'FROM games '
            'WHERE user_id = :user_id;',
            {'user_id': user_id}
        )

        if not rows:
            save_games_(db, user_id, sync_data.games)
            has_created = True

        else:
            games = {
                game.difficulty: game
                for game in sync_data.games
            }

            if len(games) != len(sync_data.games):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='There are Games with repeated Difficulty.')

            games_to_update: list[tuple[int, Game]] = []

            for row in rows:
                if row.difficulty in games:
                    if row.created_at > games[row.difficulty].created_at:
                        del games[row.difficulty]
                    else:
                        games_to_update.append((row.id, games[row.difficulty]))

            games_to_save: list[Game] = []

            _games_to_update = [game for _, game in games_to_update]
            for game in games.values():
                if game not in _games_to_update:
                    games_to_save.append(game)

            save_games_(db, user_id, games_to_save)

            if games_to_save:
                has_created = True

            for game_id, game in games_to_update:
                update_game(db, game_id, game)

    updated_time_records = get_time_records_(db, user_id)
    updated_settings = get_game_settings_(db, user_id)
    updated_games = get_games_(db, user_id)

    if any((
        not updated_time_records and sync_data.time_records,
        updated_settings is None,
        not updated_games and sync_data.games
    )):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Data could not be saved.')

    if has_created:
        response.status_code = status.HTTP_201_CREATED

    return OptionalSyncData(
        time_records=updated_time_records,
        settings=updated_settings,
        games=updated_games
    )


@router.get('/sync', response_model=OptionalSyncData)
def get_sync_data(user_id: AuthenticatedUserID, db: DBConnectionDep) -> OptionalSyncData:
    '''
    Retrieve the latest data.
    '''
    return OptionalSyncData(
        time_records=get_time_records_(db, user_id),
        settings=get_game_settings_(db, user_id),
        games=get_games_(db, user_id)
    )
