"""Create the database tables.

Importing this module only defines ``init_db``; call it (or run this file as a
script) to create the tables. Models must be imported before ``create_all`` so
they are registered on ``Base.metadata``.
"""

from app.services.database import Base, engine


def init_db() -> None:
    from app.services import dbmodel  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
