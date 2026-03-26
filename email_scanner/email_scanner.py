"""
DSLF Email Scanner — polls the "List Rental" folder in the shared Outlook mailbox,
downloads PDF attachments, and creates DSLF Jira tickets via the existing pipeline.

Auth: Microsoft Graph API with MSAL device-code flow.
      Logs in once via browser; token cached in token_cache.bin for future runs.

Usage:
    python email_scanner.py            # run once
    python email_scanner.py --loop     # run every 5 minutes (always-on)
    python email_scanner.py --login    # force re-login (clear token cache)
"""

import os
import sys
import json
import time
import logging
import argparse
import tempfile
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR  = Path(__file__).parent
_PROJECT_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_DIR))

load_dotenv(_PROJECT_DIR / ".env")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_SCRIPT_DIR / "logs" / "email_scanner.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_ID        = os.getenv("MS_CLIENT_ID", "")
TENANT_ID        = os.getenv("MS_TENANT_ID", "common")
SCOPES           = ["Mail.Read", "Mail.ReadWrite"]
TOKEN_CACHE_FILE = _SCRIPT_DIR / "token_cache.bin"
POLL_INTERVAL    = 300  # 5 minutes

SHARED_MAILBOX = os.getenv("IMAP_EMAIL", "Listfulfillment@data-management.com")
SOURCE_FOLDER  = "List Rental"
FAILED_FOLDER  = "List Rental/Failed"

SENDER_WHITELIST = {
    e.strip().lower()
    for e in os.getenv("EMAIL_WHITELIST", "robert@amlclists.com").split(",")
    if e.strip()
}

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _mailbox_base() -> str:
    return f"{GRAPH_BASE}/users/{SHARED_MAILBOX}"


# ── MSAL Auth ─────────────────────────────────────────────────────────────────

def get_access_token(force_login: bool = False) -> str:
    import msal

    if not CLIENT_ID:
        log.error("MS_CLIENT_ID not set in .env")
        sys.exit(1)

    if force_login and TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink()
        log.info("Token cache cleared.")

    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text())

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        token_cache=cache,
    )

    # Try silent refresh first
    accounts = app.get_accounts()
    if accounts and not force_login:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            if cache.has_state_changed:
                TOKEN_CACHE_FILE.write_text(cache.serialize())
            return result["access_token"]

    # Device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        log.error("Device flow failed: %s", flow)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("LOGIN REQUIRED — open the URL below and enter the code")
    print("=" * 60)
    print(flow["message"])
    print("=" * 60 + "\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        log.error("Auth failed: %s", result.get("error_description", result))
        sys.exit(1)

    if cache.has_state_changed:
        TOKEN_CACHE_FILE.write_text(cache.serialize())
    log.info("Authenticated and token cached.")
    return result["access_token"]


# ── Graph API helpers ─────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _get(token: str, url: str, params: dict = None) -> dict:
    resp = requests.get(url, headers=_headers(token), params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _patch(token: str, url: str, body: dict) -> None:
    resp = requests.patch(
        url, headers={**_headers(token), "Content-Type": "application/json"},
        json=body, timeout=20)
    resp.raise_for_status()


def _post(token: str, url: str, body: dict) -> dict:
    resp = requests.post(
        url, headers={**_headers(token), "Content-Type": "application/json"},
        json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


# ── Folder resolution ─────────────────────────────────────────────────────────

_folder_cache: dict[str, str] = {}


def _get_folder_id(token: str, folder_path: str) -> str:
    if folder_path in _folder_cache:
        return _folder_cache[folder_path]

    base      = _mailbox_base()
    parts     = folder_path.split("/")
    parent_id = "inbox"

    for part in parts:
        data    = _get(token, f"{base}/mailFolders/{parent_id}/childFolders",
                       params={"$filter": f"displayName eq '{part}'"})
        folders = data.get("value", [])
        if folders:
            parent_id = folders[0]["id"]
        else:
            created   = _post(token, f"{base}/mailFolders/{parent_id}/childFolders",
                              {"displayName": part})
            parent_id = created["id"]
            log.info("Created folder: %s", part)

    _folder_cache[folder_path] = parent_id
    return parent_id


# ── Email processing ──────────────────────────────────────────────────────────

def process_message(token: str, message: dict, failed_folder_id: str) -> None:
    from parse_pipeline import process_pdf

    msg_id  = message["id"]
    subject = message.get("subject", "(no subject)")
    sender  = message.get("from", {}).get("emailAddress", {}).get("address", "").lower()

    log.info("Processing: %r from %s", subject, sender)

    if sender not in SENDER_WHITELIST:
        log.info("Skipping — sender not in whitelist: %s", sender)
        _patch(token, f"{_mailbox_base()}/messages/{msg_id}", {"isRead": True})
        return

    data        = _get(token, f"{_mailbox_base()}/messages/{msg_id}/attachments",
                       params={"$select": "id,name,contentType,contentBytes"})
    attachments = [
        a for a in data.get("value", [])
        if a.get("name", "").lower().endswith(".pdf")
        or "pdf" in a.get("contentType", "").lower()
    ]

    if not attachments:
        log.warning("No PDF attachments in %r — marking read", subject)
        _patch(token, f"{_mailbox_base()}/messages/{msg_id}", {"isRead": True})
        return

    any_failed = False
    for att in attachments:
        att_name = att.get("name", "attachment.pdf")
        try:
            pdf_bytes = base64.b64decode(att["contentBytes"])
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            result = process_pdf(tmp_path)
            if result.get("success"):
                log.info("Ticket created: %s from %r", result.get("ticket_key"), att_name)
            else:
                log.error("Pipeline failed for %r: %s", att_name,
                          "; ".join(result.get("errors", ["unknown"])))
                any_failed = True
        except Exception as e:
            log.error("Exception on %r: %s", att_name, e)
            any_failed = True
        finally:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

    if any_failed:
        log.warning("Moving %r to Failed", subject)
        _post(token, f"{_mailbox_base()}/messages/{msg_id}/move",
              {"destinationId": failed_folder_id})
    else:
        _patch(token, f"{_mailbox_base()}/messages/{msg_id}", {"isRead": True})
        log.info("Marked as read: %r", subject)


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_scan() -> None:
    token     = get_access_token()
    source_id = _get_folder_id(token, SOURCE_FOLDER)
    failed_id = _get_folder_id(token, FAILED_FOLDER)

    data     = _get(token, f"{_mailbox_base()}/mailFolders/{source_id}/messages",
                    params={"$filter": "isRead eq false", "$top": 25,
                            "$select": "id,subject,from,receivedDateTime,hasAttachments"})
    messages = data.get("value", [])

    if not messages:
        log.info("No unread messages in '%s'.", SOURCE_FOLDER)
        return

    log.info("Found %d unread message(s).", len(messages))
    for msg in messages:
        try:
            process_message(token, msg, failed_id)
        except Exception as e:
            log.error("Error processing message: %s", e)


def main():
    parser = argparse.ArgumentParser(description="DSLF Email Scanner")
    parser.add_argument("--loop",  action="store_true",
                        help=f"Run every {POLL_INTERVAL // 60} minutes")
    parser.add_argument("--login", action="store_true",
                        help="Force re-login")
    args = parser.parse_args()

    get_access_token(force_login=args.login)

    if args.loop:
        log.info("Started — polling every %d minutes.", POLL_INTERVAL // 60)
        while True:
            try:
                run_scan()
            except Exception as e:
                log.error("Scan error: %s", e)
            time.sleep(POLL_INTERVAL)
    else:
        run_scan()


if __name__ == "__main__":
    main()
