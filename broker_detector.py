"""
Broker format detection from PDF text using regex fingerprints.

Scans the first 3000 characters. All patterns in a rule must match (AND logic).
First full match wins. Confidence is 0.92 for rule-based matches.
"""

import re
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

SCAN_LENGTH = 3000
CONFIDENCE_RULE_BASED = 0.92


@dataclass(frozen=True)
class BrokerMatch:
    broker_key: str
    confidence: float
    matched_patterns: tuple


# Each rule: (broker_key, [list of compiled regex patterns that ALL must match])
_RULES = [
    ("rkd_group", [
        re.compile(r"RKD\s+GROUP", re.IGNORECASE),
        re.compile(r"Service\s+Bureau\s+No", re.IGNORECASE),
    ]),
    ("amlc", [
        re.compile(r"American\s+Mailing\s+Lists\s+Corporation\s+Management", re.IGNORECASE),
        re.compile(r"(?:Service\s+Bureau|Purchase\s+Order)\s+No", re.IGNORECASE),
    ]),
    ("simiocloud", [
        re.compile(r"(?:Exchange|Rental)\s+Order", re.IGNORECASE),
        re.compile(r"SimioCloud", re.IGNORECASE),
    ]),
    ("data_axle", [
        re.compile(r"(?:Exchange|Rental)\s+Order", re.IGNORECASE),
        re.compile(r"Data\s+Axle", re.IGNORECASE),
    ]),
    ("rmi_direct", [
        re.compile(r"RMI\s+Direct\s+Marketing", re.IGNORECASE),
        re.compile(r"(?:Exchange|Rental)\s*Instruction", re.IGNORECASE),
    ]),
    ("celco", [
        re.compile(r"LIST\s+(?:EXCHANGE|RENTAL)\s+ORDER", re.IGNORECASE),
        re.compile(r"CELCO", re.IGNORECASE),
    ]),
    ("kap", [
        re.compile(r"LIST\s+MANAGEMENT\s+DIVISION", re.IGNORECASE),
        re.compile(r"KAP\s+ORDER", re.IGNORECASE),
    ]),
    ("washington_lists", [
        re.compile(r"Washington\s+Lists,?\s+Inc", re.IGNORECASE),
    ]),
    ("conrad_direct", [
        re.compile(r"PURCHASE\s+ORDER\s+NO:", re.IGNORECASE),
        re.compile(r"Conrad\s+Direct", re.IGNORECASE),
    ]),
    ("names_in_news", [
        re.compile(r"List\s+Order", re.IGNORECASE),
        re.compile(r"Fulfillment\s+Copy", re.IGNORECASE),
    ]),
]


def detect_broker(text: str) -> BrokerMatch | None:
    """
    Detect broker format from PDF text.

    Args:
        text: Extracted PDF text (full document).

    Returns:
        BrokerMatch with broker_key and confidence, or None if no match.
    """
    scan_text = text[:SCAN_LENGTH]

    for broker_key, patterns in _RULES:
        matched = []
        all_match = True
        for pattern in patterns:
            m = pattern.search(scan_text)
            if m:
                matched.append(m.group())
            else:
                all_match = False
                break

        if all_match:
            log.info("Broker detected: %s (patterns: %s)", broker_key, matched)
            return BrokerMatch(
                broker_key=broker_key,
                confidence=CONFIDENCE_RULE_BASED,
                matched_patterns=tuple(matched),
            )

    log.info("No broker pattern matched in first %d chars", SCAN_LENGTH)
    return None
