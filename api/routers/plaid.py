import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlmodel import Session, select

from auth import get_current_user
from crypto import decrypt_token, encrypt_token
from database import get_session
from models import PlaidItem, Transaction, User
from plaid_client import client
from schemas.plaid import (
    ExchangePublicTokenRequest,
    ExchangePublicTokenResponse,
    LinkTokenResponse,
    SyncResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plaid", tags=["plaid"])

# Plaid error codes worth surfacing as "try again shortly" rather than a hard
# failure - see https://plaid.com/docs/errors/. ITEM_LOGIN_REQUIRED is handled
# separately since retrying it can never succeed without user re-auth.
TRANSIENT_PLAID_ERROR_CODES = {
    "RATE_LIMIT_EXCEEDED",
    "PLANNED_MAINTENANCE",
    "PRODUCT_NOT_READY",
    "INTERNAL_SERVER_ERROR",
}

# Caps how many Plaid pages one HTTP request will fetch. Each page is up to
# ~500 transactions, so this bounds a single request to roughly 10k
# transactions before asking the caller to sync again to continue - without
# it, a multi-year backfill runs the whole loop inline on one worker thread
# with no upper bound on request duration.
MAX_SYNC_PAGES_PER_REQUEST = 20


def _plaid_error_code(exc: ApiException) -> str | None:
    try:
        return json.loads(exc.body).get("error_code")
    except (TypeError, ValueError, AttributeError):
        return None


@router.post("/link-token", response_model=LinkTokenResponse)
def create_link_token(current_user: User = Depends(get_current_user)):
    request = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="Expense Tracker",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=str(current_user.id)),
    )
    response = client.link_token_create(request)
    return LinkTokenResponse(link_token=response.link_token)


@router.post("/exchange-public-token", response_model=ExchangePublicTokenResponse)
def exchange_public_token(
    payload: ExchangePublicTokenRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    request = ItemPublicTokenExchangeRequest(public_token=payload.public_token)
    response = client.item_public_token_exchange(request)

    existing = session.exec(
        select(PlaidItem).where(PlaidItem.user_id == current_user.id)
    ).first()
    if existing:
        existing.item_id = response.item_id
        existing.access_token_encrypted = encrypt_token(response.access_token)
        existing.cursor = None
        session.add(existing)
    else:
        session.add(
            PlaidItem(
                user_id=current_user.id,
                item_id=response.item_id,
                access_token_encrypted=encrypt_token(response.access_token),
            )
        )
    session.commit()
    return ExchangePublicTokenResponse(connected=True)


def _category_for(txn) -> str:
    pfc = getattr(txn, "personal_finance_category", None)
    if pfc and getattr(pfc, "primary", None):
        return pfc.primary.replace("_", " ").title()
    if getattr(txn, "category", None):
        return txn.category[0]
    return "Uncategorized"


@router.post("/sync-transactions", response_model=SyncResponse)
def sync_transactions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    item = session.exec(
        select(PlaidItem).where(PlaidItem.user_id == current_user.id)
    ).first()
    if item is None:
        raise HTTPException(status_code=400, detail="No linked bank account for this user")

    added_count = modified_count = removed_count = 0
    has_more = True
    pages_fetched = 0
    access_token = decrypt_token(item.access_token_encrypted)

    while has_more and pages_fetched < MAX_SYNC_PAGES_PER_REQUEST:
        kwargs = {"access_token": access_token}
        if item.cursor is not None:
            kwargs["cursor"] = item.cursor

        try:
            response = client.transactions_sync(TransactionsSyncRequest(**kwargs))
        except ApiException as exc:
            error_code = _plaid_error_code(exc)
            logger.warning(
                "Plaid sync failed for user %s (item %s): %s",
                current_user.id, item.item_id, error_code or exc.body,
            )
            if error_code == "ITEM_LOGIN_REQUIRED":
                raise HTTPException(
                    status_code=409,
                    detail="This bank connection needs to be re-authenticated. Reconnect your account via Plaid Link.",
                ) from exc
            if error_code in TRANSIENT_PLAID_ERROR_CODES:
                raise HTTPException(
                    status_code=503,
                    detail="Plaid is temporarily unavailable. Try syncing again shortly.",
                ) from exc
            raise HTTPException(status_code=502, detail="Plaid sync failed. Try again later.") from exc

        for txn in response.added:
            session.add(
                Transaction(
                    user_id=current_user.id,
                    date=txn.date,
                    merchant=txn.merchant_name or txn.name,
                    amount=txn.amount,
                    category=_category_for(txn),
                    source="plaid",
                    plaid_transaction_id=txn.transaction_id,
                )
            )
            added_count += 1

        for txn in response.modified:
            existing = session.exec(
                select(Transaction).where(Transaction.plaid_transaction_id == txn.transaction_id)
            ).first()
            if existing:
                existing.date = txn.date
                existing.merchant = txn.merchant_name or txn.name
                existing.amount = txn.amount
                existing.category = _category_for(txn)
                session.add(existing)
                modified_count += 1

        for removed in response.removed:
            existing = session.exec(
                select(Transaction).where(Transaction.plaid_transaction_id == removed.transaction_id)
            ).first()
            if existing:
                session.delete(existing)
                removed_count += 1

        item.cursor = response.next_cursor
        has_more = response.has_more
        session.add(item)
        session.commit()
        pages_fetched += 1

    return SyncResponse(
        added=added_count,
        modified=modified_count,
        removed=removed_count,
        has_more=has_more,
    )
