"""
Alembic environment configuration.
"""

from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_metadata():
    target_db = current_app.extensions["migrate"].db
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations():
    """Run migrations against the database."""
    connectable = current_app.extensions["migrate"].db.get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **current_app.extensions["migrate"].configure_args,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
