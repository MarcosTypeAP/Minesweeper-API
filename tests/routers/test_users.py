from fastapi.testclient import TestClient
from database import DBConnection
from conftest import TestUser, assert_is_endpoint_authenticated, authenticate_requests, model2camel
from tests.routers.test_games import create_games
from tests.routers.test_times import create_time_records
from tests.routers.test_game_settings import create_game_settings
from routers.games import Game
from routers.times import TimeRecord
from typing import Any


USERS_URL = '/api/users'
ME_URL = USERS_URL + '/me'
SYNC_URL = USERS_URL + '/sync'

S_TO_MS_FACTOR = 1_000


def test_get_me(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.get, ME_URL)

    non_existing_user = TestUser(id=69420, username='#!/bin/sorareusername', password=user.password, password_hash=user.password_hash)

    with authenticate_requests(non_existing_user):
        res = client.get(ME_URL)
        assert res.status_code == 404

    with authenticate_requests(user):
        res = client.get(ME_URL)
        assert res.status_code == 200

    body = res.json()
    assert 'username' in body
    assert body['username'] == user.username


def test_get_sync_data(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.get, SYNC_URL)

    with authenticate_requests(user):
        res = client.get(SYNC_URL)
        assert res.status_code == 200

    body = res.json()

    assert body == {
        'games': None,
        'timeRecords': None,
        'settings': None
    }

    games = create_games(db, user)

    with authenticate_requests(user):
        res = client.get(SYNC_URL)
        assert res.status_code == 200

    body = res.json()

    assert body == {
        'games': model2camel(games),
        'timeRecords': None,
        'settings': None
    }

    records = create_time_records(db, user)
    game_settings = create_game_settings(db, user)

    with authenticate_requests(user):
        res = client.get(SYNC_URL)
        assert res.status_code == 200

    body = res.json()

    assert body == {
        'games': model2camel(games),
        'timeRecords': model2camel(records),
        'settings': model2camel(game_settings)
    }


def test_update_sync_data(client: TestClient, user: TestUser, db: DBConnection) -> None:

    assert_is_endpoint_authenticated(db, user, client.put, SYNC_URL)

    with authenticate_requests(user):
        res = client.put(SYNC_URL)
        assert res.status_code == 422

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json={})
        assert res.status_code == 422

    body = res.json()

    for detail in body['detail']:
        assert detail['type'] == 'missing'

        is_field_in_loc = False
        for field in ['games', 'timeRecords', 'settings']:
            if field in detail['loc']:
                is_field_in_loc = True

        assert is_field_in_loc

    games = create_games(db, user)
    records = create_time_records(db, user)
    game_settings = create_game_settings(db, user)

    data: Any = {
        'games': [],
        'timeRecords': [],
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 200

    data = {
        'games': [model2camel(games[0]) for _ in games],
        'timeRecords': [],
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 409

    data = {
        'games': [],
        'timeRecords': [model2camel(records[0]) for _ in records],
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 409

    data = {
        'games': [model2camel(games[0])],
        'timeRecords': [],
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 200

    body = res.json()

    assert body == {
        'games': model2camel(games),
        'timeRecords': model2camel(records),
        'settings': model2camel(game_settings)
    }

    games[0].created_at += 69420
    game_settings.modified_at += 69420

    r0 = records[0]
    new_record = TimeRecord(
        id=r0.id + '69',
        difficulty=r0.difficulty,
        time=r0.time,
        created_at=r0.created_at + 69420
    )

    data = {
        'games': model2camel(games),
        'timeRecords': model2camel(records + (new_record,)),
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 201

    body = res.json()

    assert body == data

    g0 = games[0]
    modified_game = Game(
        difficulty=g0.difficulty,
        encoded_game=g0.encoded_game,
        created_at=g0.created_at - 69420 * 2
    )

    data = {
        'games': model2camel(games[1:] + (modified_game,)),
        'timeRecords': model2camel(records + (new_record,)),
        'settings': model2camel(game_settings)
    }

    with authenticate_requests(user):
        res = client.put(SYNC_URL, json=data)
        assert res.status_code == 200

    body = res.json()

    assert body == {
        'games': model2camel(games),
        'timeRecords': model2camel(records + (new_record,)),
        'settings': model2camel(game_settings)
    }
