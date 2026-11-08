"""lfx-textkit: TextKit SMS and phone verification bundle.

This package is the distribution unit ``lfx-textkit``.  At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the components under namespaced IDs such as
``ext:textkit:TextKitSendMessageComponent@official``.

TextKit (https://jointextkit.com) is an SMS API; the components call its REST
API directly with ``httpx`` and need only a user-supplied API key, so the bundle
carries no vendor SDK dependency.
"""

from lfx_textkit.components.textkit import (
    TextKitCheckVerificationComponent,
    TextKitListMessagesComponent,
    TextKitSendMessageComponent,
    TextKitSendVerificationComponent,
)

__all__ = [
    "TextKitCheckVerificationComponent",
    "TextKitListMessagesComponent",
    "TextKitSendMessageComponent",
    "TextKitSendVerificationComponent",
]
