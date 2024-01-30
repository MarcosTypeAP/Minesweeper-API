from fastapi.testclient import TestClient
from routers.games import Game, save_games_
from database import DBConnection
from conftest import TestUser, assert_is_endpoint_authenticated, authenticate_requests, model2camel
from datetime import datetime, timedelta
from typing import Callable
import random

GAMES_URL = '/api/games'


Games = tuple[Game, Game, Game]


def create_games(db: DBConnection, user: TestUser, save: bool = True) -> Games:
    games = [
        Game(
            difficulty=0,
            encoded_game=str(random.randint(100, 100_000)),
            created_at=datetime.now().timestamp() + random.randint(100, 100_000)
        )
        for _ in range(3)
    ]

    games[0].difficulty = 0
    games[1].difficulty = 1
    games[2].difficulty = 2

    if save:
        save_games_(db, user.id, games)

    return games[0], games[1], games[2]


def test_get_games(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.get, GAMES_URL)

    with authenticate_requests(user):
        res = client.get(GAMES_URL)
        assert res.status_code == 404

    games = create_games(db, user)

    with authenticate_requests(user):
        res = client.get(GAMES_URL)
        assert res.status_code == 200

    body = res.json()

    fetched_games: list[Game] = [
        Game.model_validate(game)
        for game in body
    ]

    for game1, game2 in zip(games, fetched_games):
        assert game1.difficulty == game2.difficulty
        assert game1.encoded_game == game2.encoded_game
        assert game1.created_at == game2.created_at


def test_delete_games(client: TestClient, user: TestUser, db: DBConnection) -> None:
    games = create_games(db, user)
    get_url: Callable[[Game], str] = lambda game: GAMES_URL + f'/{game.difficulty}'

    assert_is_endpoint_authenticated(db, user, client.delete, get_url(games[0]))

    with authenticate_requests(user):
        res = client.delete(GAMES_URL + '/invalid_id')
        assert res.status_code == 422

    with authenticate_requests(user):
        res = client.delete(get_url(games[0]))
        assert res.status_code == 204

    rows = db.fetch_many(
        'SELECT difficulty '
        'FROM games '
        'WHERE user_id = :user_id;',
        {'user_id': user.id}
    )

    assert rows is not None

    for row in rows:
        assert row.difficulty != games[0]


def test_update_games(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.put, GAMES_URL)

    with authenticate_requests(user):
        res = client.put(GAMES_URL)
        assert res.status_code == 422

    with authenticate_requests(user):
        res = client.put(GAMES_URL, json={'encodedGame': 'invalid_game'})
        assert res.status_code == 422

    games = create_games(db, user, save=False)

    with authenticate_requests(user):
        res = client.put(GAMES_URL, json=model2camel(games[0]))
        assert res.status_code == 201

    row = db.fetch_one(
        'SELECT user_id, difficulty '
        'FROM games '
        'WHERE user_id = :user_id AND difficulty = :difficulty;',
        {'user_id': user.id, 'difficulty': games[0].difficulty}
    )
    assert row is not None

    save_games_(db, user.id, games[1:])

    initial_created_at = games[0].created_at
    games[0].created_at -= timedelta(minutes=69).seconds

    with authenticate_requests(user):
        res = client.put(GAMES_URL, json=games[0].model_dump())
        assert res.status_code == 409

    games[0].created_at = initial_created_at + timedelta(minutes=69).seconds

    with authenticate_requests(user):
        res = client.put(GAMES_URL, json=games[0].model_dump())
        assert res.status_code == 200

    row = db.fetch_one(
        'SELECT created_at '
        'FROM games '
        'WHERE user_id = :user_id AND difficulty = :difficulty;',
        {'user_id': user.id, 'difficulty': games[0].difficulty}
    )

    assert row is not None
    assert row.created_at == games[0].created_at
