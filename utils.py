from typing import Any


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
