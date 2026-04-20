#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/pg_env.sh"

"$MICROMAMBA_BIN" run -n "$PG_ENV_NAME" psql \
  -h "$PGHOST" \
  -p "$PGPORT" \
  -U "$PGUSER" \
  -d "$PGDATABASE" \
  "$@"
