import os
import sys
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context


# ============================================================
# Добавляем корень проекта в PYTHONPATH
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# Импорты проекта
# ============================================================

from config import get_settings
from models import Base


# ============================================================
# Alembic Config
# ============================================================

config = context.config


# ============================================================
# Logging
# ============================================================

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ============================================================
# Settings
# ============================================================

settings = get_settings()

DATABASE_URL = settings.database_url


# ============================================================
# Metadata
# ============================================================

target_metadata = Base.metadata


# ============================================================
# Offline migrations
# ============================================================

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In this mode Alembic does not create a real database
    connection. It generates SQL statements instead.
    """

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# Online migrations
# ============================================================

def do_run_migrations(connection) -> None:
    """
    Configure Alembic using an active database connection.
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async SQLAlchemy engine and run migrations.
    """

    # ВАЖНО:
    # Не используем config.set_main_option() для DATABASE_URL.
    #
    # В пароле Supabase может быть %3F, %40 и другие URL-encoded
    # символы. ConfigParser воспринимает % как interpolation.
    #
    # Поэтому URL передаём напрямую в словарь configuration.

    configuration = config.get_section(
        config.config_ini_section
    )

    if configuration is None:
        configuration = {}

    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            do_run_migrations
        )

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.
    """

    asyncio.run(
        run_async_migrations()
    )


# ============================================================
# Entry point
# ============================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
