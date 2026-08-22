from typing import Optional

from sqlmodel import Field, SQLModel


class PlaidItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    item_id: str
    access_token: str
    institution_name: Optional[str] = None
    cursor: Optional[str] = None
