from lfx.components.processing.pii_masking import PIIMaskingComponent
from lfx.schema.message import Message


class TestPIIMaskingComponent:
    def test_pii_masking_basic(self):
        component = PIIMaskingComponent()
        component.text_input = "My email is test@example.com and phone is 123-456-7890."
        component.mask_emails = True
        component.mask_phones = True
        component.mask_credit_cards = False
        component.mask_ssn = False
        component.mask_ip = False
        component.custom_patterns = ""
        component.replacement_template = "<{entity}>"

        result = component.get_masked_text()
        assert isinstance(result, Message)
        assert "test@example.com" not in result.text
        assert "123-456-7890" not in result.text
        assert "<EMAIL>" in result.text
        assert "<PHONE>" in result.text

    def test_pii_masking_all_types(self):
        component = PIIMaskingComponent()
        component.text_input = (
            "Email: user@host.com. Phone: +1 555-010-999. CC: 1234-5678-9012-3456. SSN: 999-00-1111. IP: 192.168.1.1"
        )
        component.mask_emails = True
        component.mask_phones = True
        component.mask_credit_cards = True
        component.mask_ssn = True
        component.mask_ip = True
        component.custom_patterns = ""
        component.replacement_template = "[MASKED_{entity}]"

        result = component.get_masked_text()
        assert "[MASKED_EMAIL]" in result.text
        assert "[MASKED_PHONE]" in result.text
        assert "[MASKED_CREDIT_CARD]" in result.text
        assert "[MASKED_SSN]" in result.text
        assert "[MASKED_IP_ADDRESS]" in result.text
        assert "user@host.com" not in result.text

    def test_custom_patterns(self):
        component = PIIMaskingComponent()
        component.text_input = "My Zip Code is 12345 and Account ID is ACC-999."
        component.mask_emails = False
        component.mask_phones = False
        component.mask_credit_cards = False
        component.mask_ssn = False
        component.mask_ip = False
        component.custom_patterns = r"\d{5}:ZIP_CODE" + "\n" + r"ACC-\d{3}:ACCOUNT_ID"
        component.replacement_template = "<{entity}>"

        result = component.get_masked_text()
        assert "<ZIP_CODE>" in result.text
        assert "<ACCOUNT_ID>" in result.text
        assert "12345" not in result.text
        assert "ACC-999" not in result.text

    def test_empty_input(self):
        component = PIIMaskingComponent()
        component.text_input = ""
        result = component.get_masked_text()
        assert result.text == ""

    def test_template_customization(self):
        component = PIIMaskingComponent()
        component.text_input = "Email me at dev@langflow.org"
        component.mask_emails = True
        component.replacement_template = "REDACTED"

        result = component.get_masked_text()
        assert result.text == "Email me at REDACTED"

    def test_invalid_custom_pattern_continues_processing(self):
        component = PIIMaskingComponent()
        component.text_input = "Email: test@example.com"
        component.mask_emails = True
        component.mask_phones = False
        component.mask_credit_cards = False
        component.mask_ssn = False
        component.mask_ip = False
        # Invalid regex pattern - unclosed bracket
        component.custom_patterns = r"[invalid:INVALID" + "\n" + r"\d{5}:ZIP"
        component.replacement_template = "<{entity}>"

        # Should not raise, invalid pattern is logged and skipped
        result = component.get_masked_text()
        assert "<EMAIL>" in result.text

    def test_no_pii_in_input(self):
        component = PIIMaskingComponent()
        component.text_input = "Hello, this is plain text with no PII."
        component.mask_emails = True
        component.mask_phones = True
        component.mask_credit_cards = True
        component.mask_ssn = True
        component.mask_ip = True
        component.custom_patterns = ""
        component.replacement_template = "<{entity}>"

        result = component.get_masked_text()
        assert result.text == "Hello, this is plain text with no PII."

    def test_ip_masking_precision(self):
        component = PIIMaskingComponent()
        # 1.1.1.1 is valid, 999.999.999.999 is invalid
        component.text_input = "Valid: 127.0.0.1, Invalid: 999.999.999.999"
        component.mask_ip = True
        component.mask_emails = False
        component.mask_phones = False
        component.mask_credit_cards = False
        component.mask_ssn = False
        component.replacement_template = "<{entity}>"

        result = component.get_masked_text()
        assert "<IP_ADDRESS>" in result.text
        assert "127.0.0.1" not in result.text
        assert "999.999.999.999" in result.text
        assert result.text.count("<IP_ADDRESS>") == 1
