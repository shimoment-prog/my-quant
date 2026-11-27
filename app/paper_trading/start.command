#!/bin/sh
set -eu
paper_app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$paper_app_dir/start.sh" "$@"
