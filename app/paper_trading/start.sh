#!/bin/sh
set -eu
paper_app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$paper_app_dir"
if [ ! -x .venv/bin/python ]; then
    printf '请先运行 ./setup.sh 创建Python环境。\n' >&2
    exit 1
fi
exec .venv/bin/python server.py "$@"
