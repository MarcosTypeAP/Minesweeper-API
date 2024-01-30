from fastapi import APIRouter, HTTPException, status, Body, Path
from database import DBConnectionDep, DBConnection
from typing import Annotated
from models import FromDBModel, CamelModel
from .auth import AuthenticatedUserID
from utils import get_json_error_resonse


class TimeRecord(FromDBModel, CamelModel):
    id: str
    difficulty: int
    time: int
    created_at: int


def save_time_records_(db: DBConnection, user_id: int, time_records: TimeRecord | list[TimeRecord]) -> None:
    if not isinstance(time_records, list):
        time_records = [time_records]

    if not time_records:
        return

    db.execute(
        'INSERT INTO time_records (id, user_id, difficulty, time, created_at) '
        'VALUES (:id, :user_id, :difficulty, :time, :created_at);',
        [
            {**record.model_dump(), 'user_id': user_id}
            for record in time_records
        ],
    )


def get_time_records_(db: DBConnection, user_id: int) -> list[TimeRecord] | None:
    rows = db.fetch_many(
        'SELECT id, difficulty, time, created_at '
        'FROM time_records '
        'WHERE user_id = :user_id;',
        {'user_id': user_id}
    )

    if not rows:
        return None

    return [
        TimeRecord.model_validate(row)
        for row in rows
    ]


not_found_exception = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No saved records found.')
id_already_exists_exception = HTTPException(status_code=status.HTTP_409_CONFLICT, detail='A TimeRecord with that ID already exists.')

router = APIRouter(tags=['Time Records'])


@router.post('/', response_model=TimeRecord, status_code=status.HTTP_201_CREATED, responses={
    status.HTTP_409_CONFLICT: get_json_error_resonse('ID already exists')
})
def save_time_record(user_id: AuthenticatedUserID, time_record: Annotated[TimeRecord, Body()], db: DBConnectionDep) -> TimeRecord:
    '''
    Providing a record with an existing 'id' will result in an error (409).
    '''
    row = db.fetch_one(
        'SELECT id '
        'FROM time_records '
        'WHERE user_id = :user_id AND id = :record_id',
        {'user_id': user_id, 'record_id': time_record.id}
    )

    if row is not None:
        raise id_already_exists_exception

    save_time_records_(db, user_id, time_record)
    return time_record


@router.delete('/{record_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_time_record(user_id: AuthenticatedUserID, record_id: Annotated[str, Path()], db: DBConnectionDep) -> None:
    db.execute(
        'DELETE FROM time_records '
        'WHERE user_id = :user_id AND id = :record_id;',
        {'user_id': user_id, 'record_id': record_id},
    )


@router.get('/', response_model=list[TimeRecord], responses={status.HTTP_404_NOT_FOUND: get_json_error_resonse()})
def get_time_records(user_id: AuthenticatedUserID, db: DBConnectionDep) -> list[TimeRecord]:
    time_records = get_time_records_(db, user_id)

    if time_records is None:
        raise not_found_exception

    return time_records
