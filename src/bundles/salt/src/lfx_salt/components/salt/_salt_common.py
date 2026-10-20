# Shared helpers for every Salt (saltapp.ai) Langflow component in this
# package: building a client, resolving an agent's own identity, the
# send helper (Salt Send Message, plain or encrypted depending on the
# room), the open-room read helper (Salt Read Room), the card-poll
# helpers behind Salt Ask Human (`get_card`, `card_id_from_post`), and the
# single-shot outbox-check helper behind Salt Read Updates
# (`check_for_event`).
#
# Deliberately thin: every real Salt call goes straight through
# `saltapp.client.SaltClient` with plain strings pulled from a component's
# field values -- no `saltapp.identity.Identity` object, no
# `saltapp.integrations.*` (that layer is built for a persistent
# framework-agent process; a Langflow component runs once per flow
# invocation, so it does not fit). See saltapp-langflow AGENTS.md for the full rationale.
#
# NO POLLING, anywhere in this module (2026-09-22 rewrite -- the owner's
# explicit rule, via the task coordinator): a Langflow component's build
# method is a single stateless call with no persistent process behind it,
# so it must never loop or sleep waiting for something to happen. The old
# `poll_for_event` (a `while True: ... time.sleep(...)` short-poll loop)
# is gone; `check_for_event` below makes exactly ONE
# `GET /api/v1/agent/updates` call per invocation and returns immediately
# with whatever it finds. Genuine push still needs a persistent process
# outside this package -- see saltapp-langflow README.md's "Push vs. on-demand" section.
#
# ONE MORE THING removed 2026-09-26: `check_for_event`/the shared outbox
# used to be how Salt Ask Human checked for its own card's tap too. It no
# longer is -- see `get_card`'s docstring below and saltapp-langflow HANDOFF.md's
# 2026-09-26 entry. `check_for_event` (and the outbox it reads) is now
# used ONLY by Salt Read Updates; Salt Ask Human reads its own card
# directly and never touches `GET /api/v1/agent/updates` at all.
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from saltapp import cards, crypto
from saltapp.client import SaltClient
from saltapp.errors import SaltApiError
from saltapp.webhook import Event, WebhookVerificationError
from saltapp.webhook import handle as handle_webhook

if TYPE_CHECKING:
    from collections.abc import Callable

SALT_HOST_DEFAULT = "https://saltapp.ai"

# Every component's optional private-key/passphrase fields carry this same
# plain-language note (rule: no "vault"/"key"/"encrypt" scare language,
# state plainly what needs a private key and what doesn't). None of the
# four components in this package ever decrypt anything: sending encrypts
# TO other people's public keys (no private key needed to do that), a
# button tap and every socket-mode event body arrive as plain structured
# JSON (never PGP ciphertext), and a payment request is a plain API record.
KEYLESS_INFO = (
    "Not needed by this component. Sending, posting and requesting only "
    "use recipients' public keys, fetched live from the chat; nothing here "
    "reads or decrypts message text."
)

# The one check_for_event round's server-side timeout, passed straight to
# GET /api/v1/agent/updates (clamped there to 0..2s regardless of what is
# sent -- see SaltClient.get_agent_updates). This is a single HTTP
# request's timeout, not a client-side retry budget -- there is no retry
# loop in this module.
_POLL_TIMEOUT_SECONDS = 2

# Deliberately NOT `saltapp.socket.SOCKET_SIGNATURE_TOLERANCE_SECONDS`: that
# constant is still the pre-round-4 widened value (7 days + 1h) as of this
# writing (see saltapp-python's own pending fix). LANES.md's round-3/4
# socket contract, "fix A" (serve-time signing): salt-api now re-signs
# every outbox row FRESH, over the stored body, at the moment it's actually
# served by GET /api/v1/agent/updates -- never once at enqueue time. So a
# row that sat unpolled for the full 7-day retention window verifies with a
# signature timestamped as if written just now, and the STANDARD ~300s
# tolerance (matching the webhook path) is correct and sufficient here too.
# The wider tolerance is a real weakness now: it would accept a signature
# far older than any genuine serve-time one could be. Defined locally
# rather than imported so this package doesn't inherit that upstream bug.
POLL_SIGNATURE_TOLERANCE_SECONDS = 300

# who_am_i answers are cached per api-key for the life of this process --
# cheap to skip re-fetching on every component run, and safe to keep stale
# for a whole process lifetime since a webhook secret only changes on an
# explicit rotation (a rotated secret just means an old cached copy fails
# verification loudly, not silently).
_WHOAMI_CACHE: dict[str, dict[str, Any]] = {}


def reset_whoami_cache() -> None:
    """Test-only: clear the per-process who_am_i cache between test cases."""
    _WHOAMI_CACHE.clear()


def get_client(host: str) -> SaltClient:
    return SaltClient(host or SALT_HOST_DEFAULT)


def resolve_identity(client: SaltClient, api_key: str) -> dict[str, Any]:
    """`who_am_i`, cached per api-key within this process (see the module docstring above the cache dict.

    for why caching is safe here).
    """
    cached = _WHOAMI_CACHE.get(api_key)
    if cached is not None:
        return cached
    info = client.who_am_i(api_key)
    _WHOAMI_CACHE[api_key] = info
    return info


def parse_options(raw: str | None) -> list[str]:
    """A comma-separated field value -> a clean list of non-empty labels."""
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def send_message(
    client: SaltClient,
    *,
    api_key: str,
    agent_id: str,
    chat_id: str,
    text: str,
    mentions: list[str] | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Post `text` into `chat_id`, choosing plain or encrypted delivery from the chat's own.

    `session.encrypted` flag (saltapp 0.2.0's open rooms): plain text via `SaltClient.post_plain_message` for
    an open (`encrypted: false`) room, PGP-encrypted-for-every-member via `send_encrypted_message` (below)
    otherwise. Missing `encrypted` defaults to True (encrypted) -- every room before 0.2.0 was encrypted and
    had no such key at all, so treating "not present" as "not open" is the safe read of an old or partial
    response shape.

    One `client.get_chat` call up front serves double duty: it is how we learn whether the room is open, and
    -- for the encrypted branch -- its `session["users"]` is the SAME member list `get_chat_members` would
    otherwise fetch with a second round trip (per saltapp-python's own `client.py`, `get_chat_members` is
    literally `get_chat(...)["session"]["users"]`). We pass that list straight through to
    `send_encrypted_message` and only fall back to a fresh `get_chat_members` call if `session` has no
    `"users"` key at all -- a defensive fallback for a response shape this SDK version does not guarantee,
    which should never actually fire today.
    """
    chat = client.get_chat(api_key, chat_id)
    session = chat.get("session") or {}

    if not session.get("encrypted", True):
        return client.post_plain_message(api_key, chat_id, text, mentions=mentions, quiet=quiet)

    members = session["users"] if "users" in session else client.get_chat_members(api_key, chat_id)
    return send_encrypted_message(
        client,
        api_key=api_key,
        agent_id=agent_id,
        chat_id=chat_id,
        text=text,
        mentions=mentions,
        quiet=quiet,
        members=members,
    )


def send_encrypted_message(
    client: SaltClient,
    *,
    api_key: str,
    agent_id: str,
    chat_id: str,
    text: str,
    mentions: list[str] | None = None,
    quiet: bool = False,
    members: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Encrypt `text` for every other member of `chat_id` and post it.

    Mirrors `SaltClient.send_message`'s own logic but takes plain strings
    instead of a `saltapp.identity.Identity` object (see the module
    docstring): fetch the chat's members, split them into "everyone but
    this agent" (the real recipients) and, if this agent's own public key
    is among the members, a self-copy so this agent's own history stays
    legible. Raises SaltApiError if nobody else in the chat has a public
    key on file yet.

    `members` lets a caller that already has the chat's member list (for
    example `send_message()` above, which fetches the chat once to read
    `session.encrypted`) pass it straight through instead of paying for a
    second `get_chat_members` round trip; omit it (the default) to fetch
    fresh, as this function always did before `send_message()` existed.
    """
    if members is None:
        members = client.get_chat_members(api_key, chat_id)
    self_id = str(agent_id or "").lower()
    recipient_keys: list[str] = []
    own_public_key: str | None = None
    for member in members:
        public_key = member.get("public_key")
        if not public_key:
            continue
        if str(member.get("id", "")).lower() == self_id:
            own_public_key = public_key
        else:
            recipient_keys.append(public_key)

    if not recipient_keys:
        no_keys = {"error": "no recipient public keys for this chat; not sending."}
        url = f"{client.host}/api/v1/messages"
        method = "POST"
        raise SaltApiError(method, url, 0, no_keys)

    encrypted = crypto.encrypt_for(text, recipient_keys)
    sender_copy = crypto.encrypt_for(text, [own_public_key]) if own_public_key else None
    return client.post_message(api_key, chat_id, encrypted, sender_copy, mentions=mentions, quiet=quiet)


def read_room(client: SaltClient, api_key: str | None, chat_id: str, last: Any = None) -> dict[str, Any]:
    """Thin wrapper over `SaltClient.get_chat` for Salt Read Room -- kept here, rather than inlined in the.

    component, for consistency with how `send_message`/`send_encrypted_message` live in this shared module
    instead of inline in theirs. `api_key` may be falsy (`""` or `None`): `SaltClient._request` then sends NO
    api-key header at all, which works read-only against a `public && !encrypted` ("open") room -- see
    `SaltClient.get_chat`'s own docstring. `last`, when given, is a message `seq` cursor: only messages newer
    than it come back, instead of the ten most recent.
    """
    return client.get_chat(api_key or "", chat_id, last=last)


def card_id_from_post(card: dict[str, Any]) -> str:
    """`POST /api/v1/cards`'s response is the card's chat BUBBLE (a Message), not the card record itself.

    `message_id` is the bubble's own id, `resource_id` is the CARD's own id (what `GET`/`PATCH
    /api/v1/cards/:id` read and update), and `resource` is the card's own `as_chat_resource` payload, which
    separately carries an `id` matching `resource_id`. There is NO top-level `id` on this response.

    A 2026-09-26 pass across every Salt integration in this workspace found the same bug in more than one
    place: reading `card["id"]` (a key that is never present) silently returned `None` forever, hidden because
    every test's fake modeled the WRONG response shape too. Fixed here the same way as salt-mcp's
    `postCardTool` (`result?.resource_id ?? result?.id ?? null`) and saltapp-agentkit's Python provider
    (`card.get("resource_id") or (card.get("resource") or {}).get("id")`) -- this mirrors the latter, since
    both read the same route.
    """
    resource = card.get("resource") or {}
    return str(card.get("resource_id") or resource.get("id") or "")


def get_card(client: SaltClient, api_key: str, card_id: str, *, after: Any = None) -> dict[str, Any]:
    """`GET /api/v1/cards/:id` (salt-api 0.96.0) -- one card's own interaction log, owner-only (404 for.

    anyone else, byte-identical to an unknown id). `interactions` comes back newest first, capped at 50
    server-side. `after` (an interaction id or an ISO8601 timestamp) asks for only interactions strictly newer
    than that; an unrecognised value fails OPEN server-side (the full list, never a 500), so a caller never
    needs to validate its own cursor before sending it.

    This is what Salt Ask Human polls now, INSTEAD OF the shared socket-mode outbox (`GET
    /api/v1/agent/updates`, `check_for_event` below) -- see saltapp-langflow HANDOFF.md's 2026-09-26 entry for
    the full story. The outbox keeps exactly ONE forward-only cursor PER AGENT: two concurrent asks against
    the same agent (or one ask beside a Salt Read Updates check, or beside any other consumer draining that
    agent's outbox) could silently consume each other's answers, because checking for one card's tap also
    advanced the cursor past every OTHER row it read. Reading one card by id is idempotent and shares nothing
    with any other ask: any number of concurrent Salt Ask Human calls, for this agent or any other agent, can
    each resolve their own ask independently.

    `saltapp.client.SaltClient` has no public `get_card` method as of saltapp 0.3.2 (confirmed: no `def
    get_card` anywhere in that package's `client.py`), and this deliberately does not add one -- another lane
    in this workspace owns `saltapp-python` and may be mid-edit on it, so this goes through `client._request`,
    the same underlying method every public `SaltClient` method is already built on, rather than editing a
    package this repo doesn't own. Mirrors saltapp-agentkit's own `_get_card` and salt-mcp's `getCard`, both
    written against this exact route for the same reason.
    """
    path = f"/api/v1/cards/{quote(str(card_id), safe='')}"
    if after is not None and after != "":
        path += f"?after={quote(str(after), safe='')}"
    return client._request("GET", path, api_key)  # noqa: SLF001 -- see docstring above


def build_question_card(question: str, options: list[str]) -> list[dict[str, Any]]:
    """A one-section, one-actions-row card: the question, then one button per option, `action_id`s.

    `opt_0`, `opt_1`, ... in the given order.
    """
    buttons = [cards.button(f"opt_{i}", label[: cards.MAX_LABEL]) for i, label in enumerate(options)]
    return cards.blocks(cards.section(text=question), cards.actions(buttons))


def _state_root() -> Path:
    override = os.environ.get("SALTAPP_LANGFLOW_STATE_DIR")
    return Path(override) if override else Path.home() / ".salt" / "agents"


def state_dir(agent_id: str, purpose: str) -> Path:
    """Where this package keeps its own small per-agent, per-purpose state (just a poll cursor so far).

    a subdirectory of the same `~/.salt/ agents/<agent_id>/` tree `saltapp.socket`'s file-backed stores use,
    kept apart under `langflow/<purpose>/` so this package's cursor files never collide with a socket-mode
    `Agent`'s own cursor/dedupe files for the same agent. Override the root with SALTAPP_LANGFLOW_STATE_DIR
    (tests do this to avoid touching a real home directory).
    """
    directory = _state_root() / (agent_id or "unknown") / "langflow" / purpose
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


# Salt Read Updates' own outbox-check cursor purpose. Used to be shared
# with Salt Ask Human (both polled the same agent's outbox through the
# same server-side ack) -- as of 2026-09-26, Salt Ask Human no longer
# reads the outbox at all (see `get_card`'s docstring above), so this is
# now the ONLY purpose any component in this package uses, and there is
# nothing left to share it WITH inside this package.
#
# It is still not safe to run two Salt Read Updates checks (or a Salt
# Read Updates check beside any OTHER consumer of this agent's outbox --
# a socket-mode `Agent`, another integration, and so on) concurrently
# against the same agent_id: salt-api keeps exactly ONE
# `agent_updates_acked_id` per agent, not one per caller, so a check with
# `after=X` moves the server's stored ack to `max(current_ack, X)`
# regardless of who sent it, and a second concurrent poller can have rows
# resolved out from under it that its own (staler) local cursor file
# still expected to see. This constant just names this package's one
# local cursor file for that one true position -- it does not add mutual
# exclusion (see saltapp-langflow AGENTS.md/saltapp-langflow README.md's "one poller per agent" warnings).
READ_UPDATES_POLL_PURPOSE = "read_updates"

# Old name, kept as an alias for one release in case anything outside
# this package's own components imported it directly. New code should use
# `READ_UPDATES_POLL_PURPOSE` -- the old name's "SHARED" was only ever
# true while Salt Ask Human also polled the outbox, which is no longer
# the case.
SHARED_POLL_PURPOSE = READ_UPDATES_POLL_PURPOSE


class PersistentCursor:
    """A tiny file-backed high-water-mark: one integer, so a later flow run (Salt Read Updates' next.

    check) does not re-scan updates an earlier run already consumed. Best-effort by design -- a missing or
    corrupt file just starts over from 0 (re-scans instead of crashing); this is a performance optimization,
    never a correctness requirement, since the caller also matches on the specific thing it is looking for (a
    requested event type).
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> int:
        try:
            return int(json.loads(self._path.read_text())["after"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return 0

    def set(self, value: int) -> None:
        try:
            self._path.write_text(json.dumps({"after": int(value)}))
            self._path.chmod(0o600)
        except OSError:
            pass  # best-effort; the next call just re-scans from its old position.


def _row_raw_bytes(update: dict[str, Any]) -> bytes:
    raw_body = update.get("body")
    if isinstance(raw_body, str):
        return raw_body.encode("utf-8")
    return json.dumps(raw_body or {}).encode("utf-8")


def check_for_event(
    client: SaltClient,
    api_key: str,
    *,
    secret: str,
    cursor: PersistentCursor,
    predicate: Callable[[Event], bool] | None = None,
    tolerance_seconds: int = POLL_SIGNATURE_TOLERANCE_SECONDS,
) -> tuple[list[Event], int]:
    """Single-shot replacement for the old `poll_for_event` sleeping loop (removed 2026-09-22 per the.

    owner's explicit "no polling, ever" rule -- see this module's own docstring, and saltapp-langflow
    AGENTS.md's "The ask/check design"). Makes exactly ONE `GET /api/v1/agent/updates` call -- no loop, no
    `time.sleep`, no wait budget of any kind -- verifies every row's signature at `tolerance_seconds`, and
    returns every event that matches `predicate` (or every verified event, if `predicate` is `None`) found in
    that one response page.

    The (local) cursor advances past every row seen in this one round -- including rows `predicate` rejected
    and rows that failed verification -- exactly like the old loop's per-round advance, so a LATER call never
    re-processes what this call already consumed. Persisted via `cursor.set(...)` before returning.

    One deliberate simplification, inherited from `poll_for_event`: a row that fails signature verification is
    skipped, not fatal -- a single on-demand call has no "next round" to retry it in, so treating an
    unverifiable row as fatal would just make this component fail outright on the next call after any one bad
    row, rather than skip past it once.

    Returns `(matches, new_cursor)`. `matches` is a list, not a single `Event` -- unlike the old loop (which
    stopped at the first predicate hit because it needed to decide whether to keep waiting), a one-shot check
    has nothing to gain by stopping early, so it collects everything this round actually saw.
    """
    after = cursor.get()
    matches: list[Event] = []

    response = client.get_agent_updates(api_key, after=after, timeout=_POLL_TIMEOUT_SECONDS, limit=100)
    updates = response.get("updates") or []
    server_cursor = response.get("cursor", after)

    for update in updates:
        row_id = update.get("id")
        headers = update.get("headers") or {}
        try:
            event = handle_webhook(
                headers,
                _row_raw_bytes(update),
                secret=secret,
                verify=True,
                tolerance_seconds=tolerance_seconds,
            )
        except WebhookVerificationError:
            if row_id is not None:
                after = row_id
            continue
        if update.get("delivery_id") is not None:
            event.delivery_id = str(update["delivery_id"])
        if update.get("created_at") is not None:
            event.created_at = str(update["created_at"])
        if row_id is not None:
            after = row_id
        if predicate is None or predicate(event):
            matches.append(event)

    new_cursor = server_cursor if server_cursor is not None else after
    cursor.set(new_cursor)

    return matches, new_cursor
