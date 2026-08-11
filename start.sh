#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head

exec python -c “import asyncio; from main import run; asyncio.run(run())”
