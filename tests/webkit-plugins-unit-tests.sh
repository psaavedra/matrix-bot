#!/usr/bin/env bash

fatal() {
    echo "Error: $1"
    exit 1
}

ROOT=$(git rev-parse --show-toplevel)

PLUGINS=(
	$ROOT/matrixbot/plugins/wkbotsfeeder.py
	$ROOT/matrixbot/plugins/wkbugsfeeder.py
	$ROOT/matrixbot/plugins/wktestbotsfeeder.py
)

which python3 &>/dev/null
if  [[ $? -ne 0 ]]; then
    fatal "Python3 is required"
fi

for each in ${PLUGINS[@]}; do
    echo -n "Testing $(realpath --relative-to=$ROOT $each): "
    content=$(python3 "$each" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "OK"
    else
        echo "Error"
        echo "$content"
        exit 1
    fi
done
