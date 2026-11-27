#!/bin/sh
set -eu
paper_app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$paper_app_dir"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
printf '\n安装完成。运行 ./start.sh 后打开 http://127.0.0.1:8088\n'
