#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head

exec python main.py
