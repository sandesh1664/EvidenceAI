from alembic import context
from app.db.base import Base
from app.db.session import get_engine
from app.core.config import get_settings
from app import models  # Register all application tables.

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Never propose dropping unrelated tables from this shared database.
    return not (type_ == "table" and reflected and compare_to is None)


if context.is_offline_mode():
    context.configure(url=get_settings().database_url.get_secret_value(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
