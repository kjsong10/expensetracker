from typing import Optional

from pydantic import BaseModel


class LinkTokenRequest(BaseModel):
    user_id: int


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangePublicTokenRequest(BaseModel):
    user_id: int
    public_token: str


class ExchangePublicTokenResponse(BaseModel):
    connected: bool
    institution_name: Optional[str] = None


class SyncRequest(BaseModel):
    user_id: int


class SyncResponse(BaseModel):
    added: int
    modified: int
    removed: int
