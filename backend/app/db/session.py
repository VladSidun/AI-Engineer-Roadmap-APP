from sqlalchemy import Engine, create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import database_url
from app.db.models import Learner


def connect() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True, hide_parameters=True)


def ensure_learner(db: Session) -> None:
    db.execute(insert(Learner).values(singleton=1).on_conflict_do_nothing(
        index_elements=[Learner.singleton],
    ))


def learner_for_update(db: Session) -> Learner:
    return db.scalars(select(Learner).where(Learner.singleton == 1).with_for_update()).one()
