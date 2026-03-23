"""Parser for AMLC broker PDF orders (same Service Bureau format as RKD Group)."""

from parsers.rkd_group import RkdGroupParser
from parsers.base import CONFIDENCE_RULE_BASED
from parse_result import ParseResult


class AmlcParser(RkdGroupParser):
    broker_key: str = "amlc"

    def parse(self, text: str) -> ParseResult:
        r = self._parse_columnar(text)
        return ParseResult(
            source=f"rule:{self.broker_key}",
            confidence=CONFIDENCE_RULE_BASED,
            mailer_name=r["mailer_name"],
            mailer_po=r["mailer_po"],
            list_name=r["list_name"],
            list_manager="AMLC",
            requested_quantity=r["requested_quantity"],
            manager_order_number=r["manager_order_number"],
            mail_date=r["mail_date"],
            ship_by_date=r["ship_by_date"],
            requestor_name=r["requestor_name"],
            requestor_email=r["requestor_email"],
            ship_to_email=r["ship_to_email"],
            key_code=r["key_code"],
            availability_rule=r["availability_rule"],
            file_format="",
            shipping_method=r["shipping_method"],
            shipping_instructions=r["shipping_instructions"],
            omission_description=r["omission_description"],
            other_fees=r["other_fees"],
            special_seed_instructions=r["special_seed_instructions"],
        )
