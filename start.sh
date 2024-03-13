#!/bin/bash

if [[ -f .env ]]; then
	IFS=$'\n'
	for line in $(grep -v '^#' .env); do
		export $line
	done
fi

if test $RUN_TESTS; then
	python3 -m pytest -p no:cacheprovider --exitfirst || exit 1
fi

if test -z "$FASTAPI_HOST"; then
	CONTAINER_IP=$(ip -4 -o address | grep -m 1 eth | sed -e "s/^[0-9]\+: \+eth[0-9]\+ \+ inet \+//" -e "s/\/.*//")

    if test -z "$(echo $CONTAINER_IP | grep -E '([0-9]+\.){3}[0-9]+')"; then
        export FASTAPI_HOST=0.0.0.0
        echo "////////////////////////////////////////////////////////////"
        echo "WARNING: Could not set \$FASTAPI_HOST. Using $FASTAPI_HOST"
        echo "////////////////////////////////////////////////////////////"
    else
        export FASTAPI_HOST=$CONTAINER_IP
    fi
fi

# Deploy service
if test -n "$PORT"; then
	export FASTAPI_PORT=$PORT
fi

if test -z "$FASTAPI_PORT"; then
	export FASTAPI_PORT=4000
    echo "////////////////////////////////////////////////////////////"
    echo "WARNING: Could not set \$FASTAPI_PORT. Using $FASTAPI_PORT"
    echo "////////////////////////////////////////////////////////////"
fi

if test "$FASTAPI_DEBUG"; then
	DEBUG_ARGS=--reload
fi

python3 -m uvicorn main:app --app-dir src $DEBUG_ARGS --port $FASTAPI_PORT --host $FASTAPI_HOST
