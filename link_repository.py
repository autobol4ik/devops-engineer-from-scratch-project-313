from sqlalchemy import Engine, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import Link, LinkPayload


class DuplicateShortNameError(Exception):
    pass


class LinkRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list_links(
        self, bounds: tuple[int, int] | None = None
    ) -> tuple[list[Link], int, int]:
        with Session(self.engine) as session:
            total = session.exec(select(func.count()).select_from(Link)).one()
            statement = select(Link).order_by(Link.id)
            start = 0
            if bounds is not None:
                start, end = bounds
                statement = statement.offset(start).limit(end - start + 1)
            links = list(session.exec(statement).all())

        return links, total, start

    def create_link(self, payload: LinkPayload) -> Link:
        link = Link.model_validate(payload)
        with Session(self.engine) as session:
            session.add(link)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise DuplicateShortNameError from error
            session.refresh(link)

        return link

    def get_link(self, link_id: int) -> Link | None:
        with Session(self.engine) as session:
            return session.get(Link, link_id)

    def update_link(self, link_id: int, payload: LinkPayload) -> Link | None:
        with Session(self.engine) as session:
            link = session.get(Link, link_id)
            if link is None:
                return None

            link.sqlmodel_update(payload.model_dump())
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise DuplicateShortNameError from error
            session.refresh(link)

        return link

    def delete_link(self, link_id: int) -> bool:
        with Session(self.engine) as session:
            link = session.get(Link, link_id)
            if link is None:
                return False

            session.delete(link)
            session.commit()

        return True

    def find_by_short_name(self, short_name: str) -> Link | None:
        with Session(self.engine) as session:
            statement = select(Link).where(Link.short_name == short_name)
            return session.exec(statement).first()
