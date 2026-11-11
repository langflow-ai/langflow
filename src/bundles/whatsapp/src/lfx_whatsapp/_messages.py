"""Fixed provider messages suitable for user-facing validation and run errors."""

SERVER_CONFIGURATION_HINT = (
    "Configure the WhatsApp app, app secret, WABA, phone ID and Graph API version on this server."
)
SYSTEM_USER_HINT = "Use this app's system-user token with both WhatsApp permissions."
PHONE_MEMBERSHIP_HINT = "The configured phone must belong to the configured WABA."
INVALID_ASSET_ID_MESSAGE = "Use a numeric WhatsApp asset ID."
INVALID_RECIPIENT_MESSAGE = "Use a recipient phone number with country code and digits only."
INVALID_MESSAGE_TEXT_MESSAGE = "Message text must contain 1 to 4096 characters."
INVALID_INBOUND_EVENT_MESSAGE = "Use a WhatsApp inbound message event."
INVALID_MESSAGE_ID_MESSAGE = "The inbound event has no valid message ID."
REPLY_PHONE_MISMATCH_MESSAGE = "Reply using the same WhatsApp business phone that received the event."
INVALID_TEMPLATE_NAME_MESSAGE = "Use an approved template name with lowercase letters, digits, and underscores."
INVALID_TEMPLATE_LANGUAGE_MESSAGE = "Use the template language code, such as en_US or pt_BR."
INVALID_BODY_PARAMETERS_MESSAGE = "Provide at most 100 nonempty text body parameters of at most 1024 characters."
MISSING_TEMPLATE_MESSAGE = "The template name or language was not found or approved on this WhatsApp Business Account."

PUBLIC_ERROR_MESSAGES = (
    SERVER_CONFIGURATION_HINT,
    SYSTEM_USER_HINT,
    PHONE_MEMBERSHIP_HINT,
    INVALID_ASSET_ID_MESSAGE,
    INVALID_RECIPIENT_MESSAGE,
    INVALID_MESSAGE_TEXT_MESSAGE,
    INVALID_INBOUND_EVENT_MESSAGE,
    INVALID_MESSAGE_ID_MESSAGE,
    REPLY_PHONE_MISMATCH_MESSAGE,
    INVALID_TEMPLATE_NAME_MESSAGE,
    INVALID_TEMPLATE_LANGUAGE_MESSAGE,
    INVALID_BODY_PARAMETERS_MESSAGE,
    MISSING_TEMPLATE_MESSAGE,
    "WhatsApp rejected the request. Check account access, recipients and message eligibility.",
)
