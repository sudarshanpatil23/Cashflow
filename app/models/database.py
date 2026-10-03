from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DATABASE_PATH = DATA_DIR / "cashflowai.db"

DATABASE_URL = (
    "sqlite:///"
    + str(DATABASE_PATH).replace("\\", "/")
)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(
        bind=engine
    )


if __name__ == "__main__":

    init_db()

    print("=" * 60)
    print("       CASHFLOWAI DATABASE")
    print("=" * 60)
    print()
    print(
        f"Database: {DATABASE_PATH}"
    )
    print()
    print("Exists:", DATABASE_PATH.exists())
    print()
    print("✓ Database initialized.")
