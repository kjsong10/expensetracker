import os

import plaid
from plaid.api import plaid_api

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

_HOST_BY_ENV = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}

configuration = plaid.Configuration(
    host=_HOST_BY_ENV.get(PLAID_ENV.lower(), plaid.Environment.Sandbox),
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)
