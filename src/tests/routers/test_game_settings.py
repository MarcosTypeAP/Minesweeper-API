from fastapi.testclient import TestClient
from database import DBConnection
from conftest import TestUser, assert_is_endpoint_authenticated, authenticate_requests, model2camel
from routers.game_settings import GameSettings, save_game_settings
import random
from datetime import datetime


GAME_SETTINGS_URL = '/api/settings'

S_TO_MS_FACTOR = 1_000


def create_game_settings(db: DBConnection, user: TestUser, save: bool = True) -> GameSettings:
    game_settings = GameSettings(
        theme=3,
        initial_zoom=False,
        action_toggle=True,
        default_action='dig',
        long_tap_delay=300,
        easy_digging=True,
        vibration=True,
        vibration_intensity=200,
        modified_at=int((datetime.now().timestamp() + random.randint(100, 100_000)) * S_TO_MS_FACTOR)
    )

    if save:
        save_game_settings(db, user.id, game_settings)

    return game_settings


def test_get_game_settings(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.get, GAME_SETTINGS_URL)

    with authenticate_requests(user):
        res = client.get(GAME_SETTINGS_URL)
        assert res.status_code == 404

    game_settings = create_game_settings(db, user)

    with authenticate_requests(user):
        res = client.get(GAME_SETTINGS_URL)
        assert res.status_code == 200

    assert res.json() == model2camel(game_settings)


def test_create_game_settings(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.put, GAME_SETTINGS_URL)

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL)
        assert res.status_code == 422

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL, json={'invalid': 'settings'})
        assert res.status_code == 422

    game_settings = create_game_settings(db, user, save=False)

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL, json=model2camel(game_settings))
        assert res.status_code == 201

    assert res.json() == model2camel(game_settings)

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL, json=model2camel(game_settings))
        assert res.status_code == 200

    game_settings.modified_at -= 69420

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL, json=model2camel(game_settings))
        assert res.status_code == 409

    game_settings.theme = 69
    game_settings.modified_at += 69420

    with authenticate_requests(user):
        res = client.put(GAME_SETTINGS_URL, json=model2camel(game_settings))
        assert res.status_code == 200

    assert res.json() == model2camel(game_settings)
