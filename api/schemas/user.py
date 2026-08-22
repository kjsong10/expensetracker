from typing import Optional

from pydantic import BaseModel


class UserPublic(BaseModel):
    id: int
    display_name: str
    email: Optional[str] = None
