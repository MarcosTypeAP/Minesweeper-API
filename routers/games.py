from fastapi import APIRouter, HTTPException, status, Body, Response, Path
from database import DBConnectionDep, DBConnection
from typing import Annotated, Sequence
from models import FromDBModel, CamelModel
from routers.auth import AuthenticatedUserID
from utils import get_json_error_resonse


class Game(FromDBModel, CamelModel):
    difficulty: int
    encoded_game: str
    created_at: float


def save_games_(db: DBConnection, user_id: int, games: Game | Sequence[Game]) -> None:
    if not isinstance(games, Sequence):
        games = [games]

    if not games:
        return

    db.execute(
        'INSERT INTO games (user_id, difficulty, encoded_game, created_at) '
        'VALUES (:user_id, :difficulty, :encoded_game, :created_at);',
        [
            {**game.model_dump(), 'user_id': user_id}
            for game in games
        ],
    )


def update_game(db: DBConnection, game_id: int, game: Game) -> None:
    db.execute(
        'UPDATE games '
        'SET difficulty = :difficulty, encoded_game = :encoded_game, created_at = :created_at '
        'WHERE id = :game_id;',
        {**game.model_dump(), 'game_id': game_id},
    )


def get_games_(db: DBConnection, user_id: int) -> list[Game] | None:
    rows = db.fetch_many(
        'SELECT difficulty, encoded_game, created_at '
        'FROM games '
        'WHERE user_id = :user_id;',
        {'user_id': user_id}
    )

    if not rows:
        return None

    return [
        Game.model_validate(row)
        for row in rows
    ]


not_found_exception = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No saved games found.')
there_is_newer_version_exception = HTTPException(status_code=status.HTTP_409_CONFLICT, detail='There is a newer version.')

router = APIRouter(tags=['Games'])


@router.put('/', response_model=Game, responses={status.HTTP_409_CONFLICT: get_json_error_resonse('Already a Newer Version')})
def save_game(user_id: AuthenticatedUserID, game: Annotated[Game, Body()], response: Response, db: DBConnectionDep) -> Game:
    '''
    Save or update the data if the provided game is more recent than the existing record.
    Otherwise, it will result in an error (409).
    '''
    row = db.fetch_one(
        'SELECT id, created_at '
        'FROM games '
        'WHERE user_id = :user_id AND difficulty = :difficulty;',
        {'user_id': user_id, 'difficulty': game.difficulty}
    )

    if row is None:
        response.status_code = status.HTTP_201_CREATED
        save_games_(db, user_id, game)
        return game

    game_id = row.id
    created_at = row.created_at

    if created_at > game.created_at:
        raise there_is_newer_version_exception

    update_game(db, game_id, game)

    return game


@router.delete('/{difficulty}', status_code=status.HTTP_204_NO_CONTENT)
def delete_game(user_id: AuthenticatedUserID, difficulty: Annotated[int, Path()], db: DBConnectionDep) -> None:
    db.execute(
        'DELETE FROM games '
        'WHERE user_id = :user_id AND difficulty = :difficulty;',
        {'user_id': user_id, 'difficulty': difficulty},
    )


@router.get('/', response_model=list[Game], responses={status.HTTP_404_NOT_FOUND: get_json_error_resonse()})
def get_games(user_id: AuthenticatedUserID, db: DBConnectionDep) -> list[Game]:
    games = get_games_(db, user_id)

    if games is None:
        raise not_found_exception

    return games
