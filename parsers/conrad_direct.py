"""Parser for Conrad Direct broker PDF orders."""

import re
from parsers.base import BaseBrokerParser, CONFIDENCE_RULE_BASED
from parse_result import ParseResult


class ConradDirectParser(BaseBrokerParser):
    broker_key: str = "conrad_direct"

    def parse(self, text: str) -> ParseResult:
        """Parse Conrad Direct purchase order PDF text."""

        # --- Purchase order number (PURCHASE ORDER NO goes in title and manager_order_number) ---
        po_number = self._find(text, r"PURCHASE\s*ORDER\s*NO:\s*(\S+)")

        # --- Order date ---
        order_date_raw = self._find(
            text, r"PURCHASE\s*ORDER\s*NO:\s*\S+\s+(\d{1,2}/\d{1,2}/\d{2,4})"
        )
        order_date = self._normalize_date(order_date_raw)

        # --- Broker ---
        broker_name = self._find(text, r"BROKER:\s*(.+?)(?:\n|$)")

        # --- Mailer ---
        mailer_name = self._find(text, r"MAILER:\s*(.+?)(?:\n|$)")

        # --- Offer ---
        offer = self._find(text, r"OFFER:\s*(.+?)(?:\n|$)")

        # --- Package ---
        package = self._find(text, r"PACKAGE:\s*(.+?)(?:\n|$)")

        # --- BROK/MAIL PO = mailer_po (primary source for duplicate check) ---
        brok_mail_po = self._find(text, r"BROK/MAIL\s*PO:\s*(.+?)(?:\n|$)")

        # --- Mail date ---
        mail_date_raw = self._find(text, r"MAIL\s*DATE:\s*(\d{1,2}/\d{1,2}/\d{2,4})")
        mail_date = self._normalize_date(mail_date_raw)

        # --- Needed By (ship_by_date) ---
        ship_by_raw = self._find(text, r"NEEDED\s*BY:?\s*(\d{1,2}/\d{1,2}/\d{2,4})")
        ship_by_date = self._normalize_date(ship_by_raw)

        # --- List name ---
        list_name = self._find(text, r"LIST:\s*(.+?)(?:\n|$)")

        # --- List manager = broker (Conrad Direct) ---
        list_manager = "Conrad Direct"

        # --- Quantity and selection ---
        # The line after LIST: contains quantity, e.g. "5,000  0-3 Mo. ..."
        qty_line = self._find(text, r"LIST:\s*[^\n]+\n\s*([\d,]+\s+.+?)(?:\n)")
        requested_quantity = 0
        availability_rule = "Nth"
        segment = ""

        if qty_line:
            num_match = re.search(r"([\d,]+)", qty_line)
            if num_match:
                requested_quantity = int(num_match.group(1).replace(",", ""))
            seg_match = re.search(r"[\d,]+\s+(.+)", qty_line)
            if seg_match:
                segment = seg_match.group(1).strip()

        if re.search(r"\*NTH\s*NAME\*", text, re.IGNORECASE):
            availability_rule = "Nth"
        if re.search(r"\*FULL\s*RUN\*", text, re.IGNORECASE):
            availability_rule = "All Available"
        if re.search(r"ALL\s+AVAILABLE", text, re.IGNORECASE):
            availability_rule = "All Available"

        # --- Mailer PO = BROK/MAIL PO (primary), fallback to MATERIAL line PO# ---
        mailer_po = brok_mail_po
        if not mailer_po:
            mat_po_match = re.search(r"PO#\s+(\S+)", text, re.IGNORECASE)
            if mat_po_match:
                mailer_po = mat_po_match.group(1).strip()
        if not mailer_po:
            mailer_po = po_number

        # --- Key Code from MATERIAL line (text after "And"/"&") ---
        # e.g., "PO# E126288 And HF Thirteen Star Flag #2215A" → key_code = "HF Thirteen Star Flag #2215A"
        key_code = ""
        mat_key_match = re.search(r"PO#\s+\S+\s+(?:And|&)\s+(.+?)(?:\n|$)", text, re.IGNORECASE)
        if mat_key_match:
            key_code = mat_key_match.group(1).strip()

        # Fallback: try explicit Key Code field
        if not key_code:
            key_code = self._find(text, r"(?:Key|KEY)\s*(?:CODE|code)?[:\s]+(\S+)")

        # --- Contact section at bottom ---
        # Format: "CONTACT: Brenda Gundlah\n          (201) 408-3683      bgundlah@conraddirect.com"
        requestor_name = ""
        requestor_email = ""
        contact_match = re.search(
            r"CONTACT:\s*(.+?)(?:\n)",
            text, re.IGNORECASE
        )
        if contact_match:
            requestor_name = contact_match.group(1).strip()
        # Find the email in the CONTACT area (after CONTACT: line)
        contact_section = self._find(text, r"CONTACT:\s*(.+?)$")
        if contact_section:
            m = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", contact_section)
            if m:
                requestor_email = m.group(1)

        # --- Ship To section ---
        ship_to_section = self._find(
            text,
            r"SHIP\s*TO:\s*(.+?)(?:TERMS:|SHIP\s*VIA:|PAYMENT|$)"
        )
        ship_to_email = ""
        if ship_to_section:
            m = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", ship_to_section)
            if m:
                ship_to_email = m.group(1)

        # --- Ship Via ---
        ship_via = self._find(text, r"SHIP\s*VIA:\s*(.+?)(?:\n|$)")
        shipping_method = self._map_shipping_method(ship_via)

        # --- Email from special instructions ---
        email_to_match = re.search(
            r"(?:Please\s+(?:Email|FTP)\s+Names?\s+To|Email\s+To|email\s+to|FTP\s+names?\s+to)[:\s]+([\w.+-]+@[\w.-]+\.\w+|https?://\S+)",
            text, re.IGNORECASE
        )
        if email_to_match:
            found_addr = email_to_match.group(1)
            if "@" in found_addr:
                if not ship_to_email:
                    ship_to_email = found_addr

        # --- Shipping instructions = CC: requestor_email (not ship-to) ---
        shipping_instructions = ""
        if requestor_email:
            shipping_instructions = f"CC: {requestor_email}"

        # --- Manager order number = PURCHASE ORDER NO ---
        manager_order_number = po_number

        # --- File format ---
        file_format = self._detect_file_format(text)

        # --- Omission description ---
        omission_description = ""
        omit_match = re.search(r"((?:Please\s+)?[Oo]mit\s+.+?)(?:\n|$)", text)
        if omit_match:
            omission_description = omit_match.group(1).strip()

        # --- Other fees: auto-detect State Omits ---
        other_fees = self._detect_state_omits(omission_description)

        # --- Billable account ---
        billable_account = ""

        # --- Seed tracking number = manager_order_number ---

        return ParseResult(
            source=f"rule:{self.broker_key}",
            confidence=CONFIDENCE_RULE_BASED,
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


