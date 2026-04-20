#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/pg_env.sh"

"$MICROMAMBA_BIN" run -n "$PG_ENV_NAME" pg_ctl \
  -D "$PGDATA" \
  status
