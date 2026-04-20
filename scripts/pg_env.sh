#!/usr/bin/env bash

set -euo pipefail

export MAMBA_ROOT_PREFIX="/mnt/hdd/cjt/local/mamba"
export MICROMAMBA_BIN="/mnt/hdd/cjt/tools/micromamba/bin/micromamba"
export PG_ENV_NAME="pg-local"
export PGDATA="/mnt/hdd/cjt/local/pgsql/data"
export PGLOG="/mnt/hdd/cjt/local/pgsql/logs/postgres.log"
export PGHOST="127.0.0.1"
export PGPORT="5432"
export PGUSER="postgres"
export PGDATABASE="ky"
