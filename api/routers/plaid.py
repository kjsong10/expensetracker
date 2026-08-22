from fastapi import APIRouter, Depends, HTTPException
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlmodel import Session, select

from auth import get_current_user
from database import get_session
from models import PlaidItem, Transaction, User
from plaid_client import client
from schemas.plaid import (
    ExchangePublicTokenRequest,
    ExchangePublicTokenResponse,
    LinkTokenResponse,
    SyncResponse,
)

router = APIRouter(prefix="/plaid", tags=["plaid"])


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
        existing.access_token = response.access_token
        existing.cursor = None
        session.add(existing)
    else:
        session.add(
            PlaidItem(
                user_id=current_user.id,
                item_id=response.item_id,
                access_token=response.access_token,
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
    cursor = item.cursor
    has_more = True

    while has_more:
        kwargs = {"access_token": item.access_token}
        if cursor is not None:
            kwargs["cursor"] = cursor
        response = client.transactions_sync(TransactionsSyncRequest(**kwargs))

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

        cursor = response.next_cursor
        has_more = response.has_more

    item.cursor = cursor
    session.add(item)
    session.commit()

    return SyncResponse(added=added_count, modified=modified_count, removed=removed_count)
