#!/bin/bash

if [[ -f .env ]]; then
	export $(cat .env)
fi

if test "$RUN_TESTS"; then
	python3 -m pytest -p no:cacheprovider --exitfirst || exit 1
fi

if test -z "$FASTAPI_HOST"; then
	local CONTAINER_IP=$(ip -4 -o address | grep -m 1 eth | sed -e "s/^[0-9]\+: \+eth[0-9]\+ \+ inet \+//" -e "s/\/.*//")
	export FASTAPI_HOST=$CONTAINER_IP
fi

if test -z "$(echo $FASTAPI_HOST | grep -E '([0-9]+\.){3}[0-9]+')"; then
	export FASTAPI_HOST=0.0.0.0
	echo //////////////////////////////////////////////////////
	echo "WARNING: Could not set \$FASTAPI_HOST". Using 0.0.0.0
	echo //////////////////////////////////////////////////////
fi

# Render deploy
if test -n "$PORT"; then
	export FASTAPI_PORT=$PORT
fi

if test "$FASTAPI_DEBUG"; then
	local DEBUG_ARGS=--reload
fi

python3 -m uvicorn main:app --app-dir src $DEBUG_ARGS --port $FASTAPI_PORT --host $FASTAPI_HOST
