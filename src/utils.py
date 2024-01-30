from typing import Any
import traceback
from pprint import pprint


def get_json_error_resonse(name: str | None = None, example: dict[str, Any] | None = None):
    return {
        'content': {
            'application/json': example if example is not None else {
                'example': {
                    'detail': 'string'
                }
            }
        },
        'description': name
    }


def print_exception(exception: Exception) -> None:
    traceback.print_tb(exception.__traceback__)
    print()
    pprint(exception.args)
