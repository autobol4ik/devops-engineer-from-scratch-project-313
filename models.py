from datetime import datetime

from pydantic import ConfigDict, StrictStr
from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel


class Link(SQLModel, table=True):
    __tablename__ = "links"

    id: int | None = Field(default=None, primary_key=True)
    original_url: str = Field(sa_column=Column(String, nullable=False))
    short_name: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True)
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class LinkPayload(SQLModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    original_url: StrictStr = Field(min_length=1)
    short_name: StrictStr = Field(min_length=1, max_length=255)
