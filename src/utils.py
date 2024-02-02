from typing import Any
import traceback
from pprint import pprint


def get_json_error_resonse(name: str | None = None, example: dict[str, Any] | None = None):
    if example is None:
        example = {
            'detail': 'string'
        }

    return {
        'content': {
            'application/json': {
                'example': example
            }
        },
        'description': name
    }


def print_exception(exception: Exception) -> None:
    traceback.print_tb(exception.__traceback__)
    print()
    pprint(exception.args)
