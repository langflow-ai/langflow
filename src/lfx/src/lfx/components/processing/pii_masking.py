import re
from typing import Any

from lfx.custom import Component
from lfx.inputs import BoolInput, MultilineInput
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class PIIMaskingComponent(Component):
    display_name = "PII Masking"
    description = "Detect and mask sensitive information (PII) like emails, phone numbers, and credit cards in text."
    icon = "shield-check"
    name = "PIIMasking"

    inputs = [
        MessageTextInput(
            name="text_input",
            display_name="Text Input",
            info="The text to be masked.",
            required=True,
        ),
        BoolInput(
            name="mask_emails",
            display_name="Mask Emails",
            info="Whether to mask email addresses.",
            value=True,
        ),
        BoolInput(
            name="mask_phones",
            display_name="Mask Phone Numbers",
            info="Whether to mask phone numbers.",
            value=True,
        ),
        BoolInput(
            name="mask_credit_cards",
            display_name="Mask Credit Cards",
            info="Whether to mask credit card numbers.",
            value=True,
        ),
        BoolInput(
            name="mask_ssn",
            display_name="Mask SSN",
            info="Whether to mask Social Security Numbers.",
            value=True,
        ),
        BoolInput(
            name="mask_ip",
            display_name="Mask IP Addresses",
            info="Whether to mask IPv4 addresses.",
            value=True,
        ),
        MultilineInput(
            name="custom_patterns",
            display_name="Custom Patterns",
            info="Additional regex patterns to mask (one per line). Format: pattern:label",
            placeholder="[0-9]{5}:ZIP_CODE",
        ),
        MultilineInput(
            name="replacement_template",
            display_name="Replacement Template",
            info="The template used for masking. Use {entity} as a placeholder.",
            value="<{entity}>",
        ),
    ]

    outputs = [
        Output(display_name="Masked Text", name="masked_message", method="get_masked_text"),
    ]

    # Predefined PII Regex Patterns
    PII_PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "PHONE": r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    def get_masked_text(self) -> Message:
        text = self.text_input
        if not text:
            return Message(text="")

        masked_text = text
        template = self.replacement_template or "<{entity}>"

        # Apply predefined patterns in order from most specific to least specific
        # to avoid overlapping matches (e.g., phone matching part of an IP)
        
        if self.mask_credit_cards:
            masked_text = re.sub(self.PII_PATTERNS["CREDIT_CARD"], template.format(entity="CREDIT_CARD"), masked_text)

        if self.mask_ssn:
            masked_text = re.sub(self.PII_PATTERNS["SSN"], template.format(entity="SSN"), masked_text)

        if self.mask_ip:
            masked_text = re.sub(self.PII_PATTERNS["IP_ADDRESS"], template.format(entity="IP_ADDRESS"), masked_text)

        if self.mask_emails:
            masked_text = re.sub(self.PII_PATTERNS["EMAIL"], template.format(entity="EMAIL"), masked_text)
        
        if self.mask_phones:
            # Refined phone regex to avoid matching IP parts by making separators more specific
            phone_pattern = r"\+?\d{1,4}?[-\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}"
            masked_text = re.sub(phone_pattern, template.format(entity="PHONE"), masked_text)

        # Apply custom patterns
        custom_patterns_text = self.custom_patterns
        if custom_patterns_text:
            for line in custom_patterns_text.split("\n"):
                if not line.strip() or ":" not in line:
                    continue
                try:
                    pattern, label = line.split(":", 1)
                    masked_text = re.sub(pattern.strip(), template.format(entity=label.strip()), masked_text)
                except Exception as e:
                    self.log(f"Error applying custom pattern '{line}': {e}")

        self.status = masked_text
        return Message(text=masked_text)
