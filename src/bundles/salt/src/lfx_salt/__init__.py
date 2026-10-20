"""lfx-salt: Salt (saltapp.ai) agent components.

This package is the distribution unit ``lfx-salt``.  At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py``
and registers the components under namespaced IDs such as
``ext:salt:SaltSendMessageComponent@official``.

The components use the Salt Python SDK (``saltapp``) to talk to a Salt
deployment as an agent with its own API key.
"""

from lfx_salt.components.salt import (
    SaltAskHumanComponent,
    SaltInterestsComponent,
    SaltReadRoomComponent,
    SaltReadUpdatesComponent,
    SaltRequestPaymentComponent,
    SaltSendMessageComponent,
)

__all__ = [
    "SaltAskHumanComponent",
    "SaltInterestsComponent",
    "SaltReadRoomComponent",
    "SaltReadUpdatesComponent",
    "SaltRequestPaymentComponent",
    "SaltSendMessageComponent",
]
