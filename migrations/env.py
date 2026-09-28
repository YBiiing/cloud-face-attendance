from alembic import context
from app.config import Settings
from app.database import Base, make_engine
import app.models  # noqa: F401

engine = make_engine(Settings.from_env())
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
