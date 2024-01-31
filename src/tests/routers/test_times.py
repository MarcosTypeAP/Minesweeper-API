from fastapi.testclient import TestClient
from database import DBConnection
from conftest import TestUser, assert_is_endpoint_authenticated, authenticate_requests, model2camel
from routers.times import TimeRecord, save_time_records_
import random
from datetime import datetime


TimeRecords = tuple[TimeRecord, TimeRecord, TimeRecord]


TIMES_URL = '/api/timerecords'

S_TO_MS_FACTOR = 1_000


def create_time_records(db: DBConnection, user: TestUser, save: bool = True) -> TimeRecords:
    records = [
        TimeRecord(
            id=str(random.randint(100_000, 1_000_000)),
            difficulty=random.randint(0, 5),
            time=random.randint(10, 1_000),
            created_at=int((datetime.now().timestamp() + random.randint(100, 100_000)) * S_TO_MS_FACTOR)
        )
        for _ in range(3)
    ]

    records[0].id += '0'
    records[1].id += '1'
    records[2].id += '2'

    if save:
        save_time_records_(db, user.id, records)

    return records[0], records[1], records[2]


def test_delete_time_records(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.delete, TIMES_URL + '/id')

    with authenticate_requests(user):
        res = client.delete(TIMES_URL + '/69')
        assert res.status_code == 204

    records = create_time_records(db, user)

    rows = db.fetch_many(
        'SELECT 1 '
        'FROM time_records '
        'WHERE user_id = :user_id AND id = :record_id;',
        {'user_id': user.id, 'record_id': records[0].id}
    )
    assert rows

    with authenticate_requests(user):
        res = client.delete(TIMES_URL + f'/{records[0].id}')
        assert res.status_code == 204

    rows = db.fetch_many(
        'SELECT 1 '
        'FROM time_records '
        'WHERE user_id = :user_id AND id = :record_id;',
        {'user_id': user.id, 'record_id': records[0].id}
    )
    assert not rows


def test_get_time_records(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.get, TIMES_URL)

    with authenticate_requests(user):
        res = client.get(TIMES_URL)
        assert res.status_code == 200

    assert res.json() == [] 

    records = create_time_records(db, user)

    with authenticate_requests(user):
        res = client.get(TIMES_URL)
        assert res.status_code == 200

    assert res.json() == model2camel(records)


def test_create_time_records(client: TestClient, user: TestUser, db: DBConnection) -> None:
    assert_is_endpoint_authenticated(db, user, client.post, TIMES_URL)

    with authenticate_requests(user):
        res = client.post(TIMES_URL)
        assert res.status_code == 422

    with authenticate_requests(user):
        res = client.post(TIMES_URL, json={'id': 'invalid_record'})
        assert res.status_code == 422

    records = create_time_records(db, user, save=False)

    with authenticate_requests(user):
        res = client.post(TIMES_URL, json=model2camel(records[0]))
        assert res.status_code == 201

    with authenticate_requests(user):
        res = client.post(TIMES_URL, json=model2camel(records[0]))
        assert res.status_code == 409
