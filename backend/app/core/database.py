from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(settings.db_url, connect_args={"check_same_thread": False, "timeout": 30}, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    for pragma in ["PRAGMA foreign_keys=ON", "PRAGMA journal_mode=WAL", "PRAGMA busy_timeout=30000", "PRAGMA synchronous=NORMAL"]:
        cursor.execute(pragma)
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
