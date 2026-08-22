from typing import Optional

from pydantic import BaseModel


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangePublicTokenRequest(BaseModel):
    public_token: str


class ExchangePublicTokenResponse(BaseModel):
    connected: bool
    institution_name: Optional[str] = None


class SyncResponse(BaseModel):
    added: int
    modified: int
    removed: int
