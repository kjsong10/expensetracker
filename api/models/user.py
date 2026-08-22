from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class User(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_subject", name="uq_user_oauth_identity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: str
    email: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_subject: Optional[str] = None
