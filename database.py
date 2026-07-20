import os

from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine


def create_db_engine(database_url=None):
    url = make_url(database_url or os.getenv("DATABASE_URL", "sqlite://"))
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")

    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        if url.database in {None, ""}:
            options["poolclass"] = StaticPool

    return create_engine(url, **options)


def create_tables(engine: Engine):
    SQLModel.metadata.create_all(engine)
