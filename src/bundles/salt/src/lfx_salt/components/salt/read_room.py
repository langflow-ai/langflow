# Salt Read Room: on-demand read of a chat's session + messages, with an
# optional `last` cursor for a catch-up window (saltapp 0.2.0's
# `GET /api/v1/chats/:id?last=`, wrapped by _salt_common.read_room). Every
# returned message already carries `encrypted`/`delivered_because`
# verbatim from salt-api -- this component passes them through as-is,
# never recomputes them.
#
# Works fully keyless: `api_key` is optional (blank sends no api-key
# header at all), which reads a public, unencrypted ("open") room with no
# identity whatsoever -- see SaltClient.get_chat's own docstring. Anything
# else with a blank key still 404s, indistinguishably from "not found".
#
# This is the on-demand "read new since cursor" half of the push/pull
# pairing described in saltapp-langflow README.md's "Push vs. on-demand" section -- it
# never blocks waiting for a new message; call it again with `last` set
# to the newest `seq` you have already seen. Genuine push into a running
# flow needs a persistent process outside this package; see that section.
#
# No private_key/passphrase fields: unlike the other components in this
# package, which keep those two fields present-but-unused for a
# consistent field layout (see saltapp-langflow AGENTS.md, "The keyless boundary"), this
# component returns the room's raw messages as-is -- ciphertext included,
# for an encrypted room -- and structurally never decrypts anything, so
# there is no future path where it would start using them either.
from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx_salt.components.salt import _salt_common as sc


class SaltReadRoomComponent(Component):
    display_name = "Salt Read Room"
    description = "Read a Salt chat's session and messages on demand, optionally since a cursor."
    icon = "inbox"
    name = "SaltReadRoom"

    inputs = [
        StrInput(
            name="host",
            display_name="Salt Host",
            value=sc.SALT_HOST_DEFAULT,
            info="The Salt deployment this agent is registered on.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=False,
            info=(
                'This agent\'s Salt API key. Leave blank to read a public, unencrypted ("open") room '
                "with no identity at all -- anything else with a blank key still 404s, same as a genuine "
                "not-found."
            ),
        ),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            tool_mode=True,
            info="The Salt chat to read.",
        ),
        MessageTextInput(
            name="last",
            display_name="Last",
            required=False,
            info="Only return messages newer than this cursor (a message seq); leave blank for the ten most recent.",
        ),
    ]

    outputs = [Output(display_name="Room", name="room", method="read")]

    def read(self) -> Data:
        client = sc.get_client(self.host)
        try:
            chat = sc.read_room(client, self.api_key, self.chat_id, last=self.last or None)
        finally:
            client.close()

        messages = chat.get("messages") or []
        self.status = f"{len(messages)} message(s) in chat {self.chat_id}."
        return Data(data=chat)
