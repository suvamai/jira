"""Parser for Data Axle broker PDF orders."""

import re
from parsers.base import BaseBrokerParser, CONFIDENCE_RULE_BASED
from parse_result import ParseResult


class DataAxleParser(BaseBrokerParser):
    broker_key: str = "data_axle"

    def parse(self, text: str) -> ParseResult:
        """Parse Data Axle rental/exchange order PDF text."""

        # --- Order number ---
        # Format: "Order # 2321545-Laura" or "Order # 58128-"
        manager_order_number = self._find(text, r"Order\s*#\s*(\d+)")
        key_code_from_order = self._find(text, r"Order\s*#\s*\d+-(\S+)")

        # --- Mailer PO and list abbreviation from Ship Label ---
        # Ship Label formats:
        #   "PO:58364-RN/SHSM/Graymoor..." → mailer_po = "58364-RN", list_abbrev = "SHSM"
        #   "Wounded Warrior_Blue Star Families_May 2026_Qty_220151" → mailer_po = "220151"
        ship_label = self._find(text, r"Ship\s*Label[:\s]*([^\n]+)")
        mailer_po = ""
        list_abbreviation = ""
        if ship_label:
            # Try PO: prefix first — capture everything up to / or whitespace
            m = re.search(r"PO[:\s]*([^/\s]+)", ship_label, re.IGNORECASE)
            if m:
                mailer_po = m.group(1).strip()
                # Extract list abbreviation: second /-delimited segment (e.g., SHSM)
                parts = ship_label.split("/")
                if len(parts) >= 2:
                    list_abbreviation = parts[1].strip()
            else:
                # Fallback: extract standalone number (e.g., from "Qty_220151")
                m = re.search(r"(\d{4,})", ship_label)
                if m:
                    mailer_po = m.group(1)
        # Fallback to Order # if no ship label PO found
        if not mailer_po:
            mailer_po = manager_order_number

        # Explicit Key Code line overrides
        key_code = self._find(text, r"Key\s*Code:\s*([^\n]+)")
        if not key_code:
            key_code = key_code_from_order

        # --- Order type ---
        order_type = ""
        if re.search(r"Rental\s+Order", text, re.IGNORECASE):
            order_type = "Rental"
        elif re.search(r"Exchange\s+Order", text, re.IGNORECASE):
            order_type = "Exchange"

        # --- List manager = broker ("From:" company, first line only) ---
        list_manager = self._find(text, r"From:\s*\n\s*([^\n]+)")

        # --- From: contact info (the broker) ---
        from_company = self._find(text, r"From:\s*\n\s*(.+)")
        from_contact = ""
        from_email = ""
        from_section = self._find(text, r"From:\s*\n(.+?)(?:Mailer:)", group=1)
        if from_section:
            m = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", from_section)
            if m:
                from_email = m.group(1)
            # First line after company name is the contact
            from_lines = [ln.strip() for ln in from_section.strip().split("\n") if ln.strip()]
            if len(from_lines) >= 2:
                from_contact = from_lines[1]

        # --- Mailer ---
        mailer_name = self._find(text, r"Mailer:\s*(.+?)(?:\n|$)")

        # --- Offer ---
        offer = self._find(text, r"Offer:\s*([^\n]+)")

        # --- Mail date ---
        mail_date_raw = self._find(text, r"Mail\s*Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})")
        mail_date = self._normalize_date(mail_date_raw)

        # --- List name (Media field) ---
        list_name = self._find(text, r"Media:\s*(.+?)(?:\n\s*(?:Test|Base|Selects|Addressing))", group=1)
        if not list_name:
            list_name = self._find(text, r"Media:\s*([^\n]+)")
        # Clean up multi-line
        list_name = re.sub(r"\s*\n\s*", " ", list_name).strip()

        # --- Quantity and availability ---
        requested_quantity, availability_rule = self._find_quantity(
            text, r"Order\s*Quantity:\s*(.+)"
        )

        # --- Ship by date (Needed By) ---
        ship_by_raw = self._find(text, r"Needed\s*By:\s*(\d{1,2}/\d{1,2}/\d{2,4})")
        ship_by_date = self._normalize_date(ship_by_raw)

        # --- Shipping method ---
        shipping_via = self._find(text, r"Shipping\s*Via:\s*([^\n]+)")
        if not shipping_via:
            shipping_via = self._find(text, r"Ship\s*Via:\s*([^\n]+)")
        shipping_method = self._map_shipping_method(shipping_via)

        # --- Ship to email ---
        ship_to_section = self._find(text, r"Ship\s*to:\s*(.+?)(?:Special\s*Instructions|$)", group=1)
        ship_to_email = ""
        if ship_to_section:
            m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", ship_to_section)
            if m:
                ship_to_email = m.group()

        # --- Requestor: use From: contact (the broker contact) ---
        requestor_name = from_contact if from_contact else ""
        requestor_email = from_email if from_email else ship_to_email

        # --- Shipping instructions = CC: requestor_email ---
        shipping_instructions = ""
        if requestor_email:
            shipping_instructions = f"CC: {requestor_email}"

        # --- File format ---
        file_format = self._detect_file_format(text)

        # --- Omission description ---
        omission_description = ""
        special = self._find(text, r"Special\s*Instructions:\s*(.+)", group=1)
        if special:
            omit_match = re.search(r"(OMIT\s+.+?)(?:\n|$)", special, re.IGNORECASE)
            if omit_match:
                omission_description = omit_match.group(1).strip()
        if not omission_description:
            omit_match = re.search(r"(OMIT\s+.+?)(?:\n|$)", text, re.IGNORECASE)
            if omit_match:
                omission_description = omit_match.group(1).strip()

        # --- Other fees: explicit field first, then auto-detect State Omits ---
        other_fees = self._find(text, r"Other\s*Fees:[ \t]*([^\n]+)")
        if not other_fees:
            other_fees = self._detect_state_omits(omission_description)

        # --- Billable account ---
        billable_account = ""

        # --- Summary: use abbreviation if available, e.g., "P.O. 2316747 SHSM" ---
        summary = ""
        if list_abbreviation and manager_order_number:
            summary = f"P.O. {manager_order_number} {list_abbreviation}"

        return ParseResult(
            source=f"rule:{self.broker_key}",
            confidence=CONFIDENCE_RULE_BASED,
            summary=summary,
            mailer_name=mailer_name,
            mailer_po=mailer_po,
            list_name=list_name,
            list_manager=list_manager,
            requested_quantity=requested_quantity,
            manager_order_number=manager_order_number,
            mail_date=mail_date,
            ship_by_date=ship_by_date,
            requestor_name=requestor_name,
            requestor_email=requestor_email,
            ship_to_email=ship_to_email,
            key_code=key_code,
            billable_account=billable_account,
            availability_rule=availability_rule,
            file_format=file_format,
            shipping_method=shipping_method,
            shipping_instructions=shipping_instructions,
            omission_description=omission_description,
            other_fees=other_fees,
        )

