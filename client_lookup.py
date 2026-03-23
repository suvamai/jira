"""
Client lookup from Excel file (NEW LR CLIENT LIST 2026 1.xlsx).

Enriches billable_account and list_manager from the client database.
Lookup order: exact db_code match first, then fuzzy name match (>=50% word overlap).
"""

import os
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Default Excel file location
_DEFAULT_EXCEL = Path(__file__).parent / "broker_pdf" / "NEW LR CLIENT LIST 2026 1.xlsx"

_client_cache: list | None = None
_WORD_CLEAN_RE = re.compile(r"[^a-z0-9 ]")


def _load_all_clients(excel_path: str = None) -> list[dict]:
    """Load all rows from the client Excel file. Cached after first call."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    path = excel_path or str(_DEFAULT_EXCEL)

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active

        clients = []
        for row in ws.iter_rows(min_row=2, max_col=8, values_only=True):
            db_code = str(row[0] or "").strip()
            billing_cust = str(row[1] or "").strip()
            db_name = str(row[2] or "").strip()
            rental_name = str(row[3] or "").strip()
            list_manager = str(row[4] or "").strip()
            lm_contact = str(row[5] or "").strip()

            if db_code or billing_cust:
                clients.append({
                    "db_code": db_code,
                    "billing_cust": billing_cust,
                    "db_name": db_name,
                    "rental_name": rental_name,
                    "list_manager": list_manager,
                    "lm_contact": lm_contact,
                })

        wb.close()
        log.info("Loaded %d clients from Excel", len(clients))
        _client_cache = clients
        return _client_cache

    except Exception as e:
        log.warning("Failed to load client Excel: %s", e)
        _client_cache = []
        return _client_cache


def _word_overlap(a: str, b: str) -> float:
    """Calculate word overlap ratio between two strings."""
    words_a = set(_WORD_CLEAN_RE.sub(" ", a.lower()).split())
    words_b = set(_WORD_CLEAN_RE.sub(" ", b.lower()).split())
    # Filter short words
    words_a = {w for w in words_a if len(w) > 2}
    words_b = {w for w in words_b if len(w) > 2}
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def get_billable_account(list_name: str = "", db_code: str = "") -> dict:
    """
    Look up billable account and list manager from Excel.

    Returns dict with keys: billable_account, list_manager, db_code, lm_contact.
    Empty dict if no match found.
    """
    clients = _load_all_clients()
    if not clients:
        return {}

    # 1. Exact match by db_code
    if db_code:
        for c in clients:
            if c["db_code"].upper() == db_code.upper():
                return {
                    "billable_account": c["billing_cust"],
                    "list_manager": c["list_manager"],
                    "db_code": c["db_code"],
                    "lm_contact": c["lm_contact"],
                }

    # 2. Fuzzy name match on rental_name / db_name
    if list_name:
        best_match = None
        best_score = 0.0
        for c in clients:
            for field in ("rental_name", "db_name"):
                val = c.get(field, "")
                if not val:
                    continue
                score = _word_overlap(list_name, val)
                if score > best_score:
                    best_score = score
                    best_match = c

        if best_match and best_score >= 0.5:
            return {
                "billable_account": best_match["billing_cust"],
                "list_manager": best_match["list_manager"],
                "db_code": best_match["db_code"],
                "lm_contact": best_match["lm_contact"],
            }

    return {}


def enrich_fields(list_name: str = "", db_code: str = "") -> dict:
    """
    Enrich fields from Excel client list.

    This is the main entry point used by parse_pipeline.py and orchestrator.py.
    Returns dict with billable_account, list_manager, db_code, lm_contact.
    """
    return get_billable_account(list_name=list_name, db_code=db_code)
