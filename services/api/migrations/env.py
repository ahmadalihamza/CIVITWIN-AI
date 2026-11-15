from alembic import context
from app.config import Settings
from app.db.models import Base


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(
            url=Settings.from_env().database_url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    if (connection := context.config.attributes.get("connection")) is not None:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    from app.db.store import Store, backup_database

    store = Store(Settings.from_env())
    try:
        if store.path is not None:
            backup_database(store.path)
        with store.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()
    finally:
        store.close()


run_migrations()
