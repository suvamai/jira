"""
Validate a ParseResult before Jira ticket creation.

Hard errors block ticket creation.
Warnings are logged but do not block.
"""

import re
import logging
from dataclasses import dataclass, field
from parse_result import ParseResult

log = logging.getLogger(__name__)

VALID_AVAILABILITY = {"Nth", "All Available"}
VALID_FILE_FORMAT = {"ASCII Delimited", "ASCII Fixed", "Excel", "Other"}
VALID_SHIPPING_METHOD = {"Email", "FTP", "Other"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def validate_result(result: ParseResult) -> ValidationResult:
    """
    Validate a ParseResult.

    Returns ValidationResult with valid=False if hard errors found.
    """
    v = ValidationResult()

    # --- Hard errors (block ticket creation) ---

    # Required text fields
    for fld, label in [
        ("mailer_name", "Mailer Name"),
        ("mailer_po", "Mailer PO"),
        ("list_name", "List Name"),
        ("list_manager", "List Manager"),
    ]:
        val = getattr(result, fld, "")
        if not val or not val.strip():
            v.errors.append(f"Missing required field: {label}")
            v.valid = False

    # Required quantity
    if not result.requested_quantity or result.requested_quantity <= 0:
        v.errors.append("Missing or zero requested_quantity")
        v.valid = False

    # Date format validation
    for fld, label in [("mail_date", "Mail Date"), ("ship_by_date", "Ship By Date")]:
        val = getattr(result, fld, "")
        if val and not DATE_PATTERN.match(val):
            v.errors.append(f"Invalid date format for {label}: {val!r} (expected YYYY-MM-DD)")
            v.valid = False

    # Enum validation
    if result.availability_rule and result.availability_rule not in VALID_AVAILABILITY:
        v.errors.append(f"Invalid availability_rule: {result.availability_rule!r}")
        v.valid = False

    if result.file_format and result.file_format not in VALID_FILE_FORMAT:
        v.errors.append(f"Invalid file_format: {result.file_format!r}")
        v.valid = False

    if result.shipping_method and result.shipping_method not in VALID_SHIPPING_METHOD:
        v.errors.append(f"Invalid shipping_method: {result.shipping_method!r}")
        v.valid = False

    # --- Warnings (logged, do not block) ---

    # Suspicious email
    for fld in ("requestor_email", "ship_to_email"):
        val = getattr(result, fld, "")
        if val and not re.match(r"^[\w.+-]+@[\w.-]+\.\w+$", val):
            v.warnings.append(f"Suspicious email format in {fld}: {val!r}")

    # Missing optional dates
    if not result.mail_date:
        v.warnings.append("Missing mail_date")
    if not result.ship_by_date:
        v.warnings.append("Missing ship_by_date")

    # No email addresses at all
    if not result.requestor_email and not result.ship_to_email:
        v.warnings.append("No email addresses found")

    return v
