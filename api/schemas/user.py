from pydantic import BaseModel


class UserCreate(BaseModel):
    display_name: str
