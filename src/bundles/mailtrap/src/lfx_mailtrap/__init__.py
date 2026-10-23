"""lfx-mailtrap: Mailtrap email bundle.

This package is the distribution unit ``lfx-mailtrap``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers each component under a namespaced ID such as
``ext:mailtrap:MailtrapSendEmailComponent@official``.

Mailtrap (https://mailtrap.io) is an email platform.  The components send
email through the Email API (Transactional and Bulk streams) and test it in
the Email Sandbox.  They call Mailtrap through the official ``mailtrap``
Python SDK and need only a user-supplied API token.
"""

from lfx_mailtrap.components.mailtrap import (
    MailtrapCheckSandboxMessageComponent,
    MailtrapGetSandboxMessageComponent,
    MailtrapListSandboxMessagesComponent,
    MailtrapSendEmailComponent,
)

__all__ = [
    "MailtrapCheckSandboxMessageComponent",
    "MailtrapGetSandboxMessageComponent",
    "MailtrapListSandboxMessagesComponent",
    "MailtrapSendEmailComponent",
]
