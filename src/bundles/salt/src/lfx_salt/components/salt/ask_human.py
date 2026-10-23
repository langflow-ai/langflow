# Salt Ask Human: post a card with button options into a Salt chat, then
# check ONCE for a tap and always return -- either the answer, or a
# pending result carrying the card's id so a LATER flow run (this same
# component, re-invoked with `card_id` set) can check again. There is no
# waiting here: a Langflow component's build method is a single stateless
# call with no persistent process behind it, and per the owner's explicit
# rule this package must never loop or sleep waiting for something to
# happen. See saltapp-langflow AGENTS.md ("The ask/check design") for the full write-up,
# and saltapp-langflow README.md's "Push vs. on-demand" section for what changes if you
# need a genuine wait-then-answer instead of this check-yourself shape.
#
# Reads the TAPPED CARD's own interaction log (salt-api 0.96.0,
# `GET /api/v1/cards/:id`, via `_salt_common.get_card`) -- NEVER the
# shared socket-mode outbox (`GET /api/v1/agent/updates`). See
# `_salt_common.get_card`'s docstring and saltapp-langflow HANDOFF.md's 2026-09-26 entry
# for the full story: that outbox keeps exactly ONE forward-only cursor
# PER AGENT, so two concurrent asks against the same agent (or one ask
# beside a Salt Read Updates check, or beside any other listener draining
# that agent's outbox) could silently consume each other's answers, and
# any `after` one of them sent permanently advanced the OTHER's
# server-side position. Polling one card by id is idempotent and shares
# nothing with any other ask: any number of concurrent Salt Ask Human
# calls, for this agent or any other, can each resolve their own ask
# independently.
from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineSecretInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message
from lfx_salt.components.salt import _salt_common as sc
from saltapp.errors import SaltApiError

HTTP_TOO_MANY_REQUESTS = 429


class SaltAskHumanComponent(Component):
    display_name = "Salt Ask Human"
    description = (
        "Post a question with button options into a Salt chat and check once for a tap. "
        "Returns the tapped option if one is already there, or a pending result to check again later. "
        "Polls its own card, never this agent's shared outbox, so any number of these can run "
        "concurrently."
    )
    icon = "help-circle"
    name = "SaltAskHuman"

    inputs = [
        StrInput(
            name="host",
            display_name="Salt Host",
            value=sc.SALT_HOST_DEFAULT,
            info="The Salt deployment this agent is registered on.",
        ),
        StrInput(
            name="agent_id",
            display_name="Agent ID",
            required=False,
            info="This agent's own Salt id. Kept for consistency with the other Salt components; not sent "
            "to the API and not used to check for a tap -- this component reads its own card directly, "
            "never a per-agent cursor.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="This agent's Salt API key.",
        ),
        MultilineSecretInput(
            name="private_key",
            display_name="Agent Private Key (optional)",
            required=False,
            info=(
                "Not needed here, even to read the answer: a tapped button arrives as plain "
                f"structured data, never PGP ciphertext. {sc.KEYLESS_INFO}"
            ),
        ),
        SecretStrInput(
            name="passphrase",
            display_name="Private Key Passphrase (optional)",
            required=False,
            info="Not needed here -- this component never decrypts anything.",
        ),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            tool_mode=True,
            info="The Salt chat to ask in.",
        ),
        MessageTextInput(
            name="question",
            display_name="Question",
            tool_mode=True,
            required=False,
            info="The question shown on the card. Only used when card_id is blank (posting a new question).",
        ),
        MessageTextInput(
            name="options",
            display_name="Options",
            value="Yes,No",
            tool_mode=True,
            info='Comma-separated button labels, 1 to 5, e.g. "Yes,No" or "staging,production". '
            "Required when card_id is blank; not needed to re-check an existing card (a recheck still "
            "matches any tap on that card).",
        ),
        MessageTextInput(
            name="card_id",
            display_name="Card ID (to re-check)",
            required=False,
            tool_mode=True,
            info=(
                "Leave blank to post a new question. Fill in a card_id from a previous pending result of "
                "this same component to check whether it's been answered yet, without posting a new card."
            ),
        ),
    ]

    outputs = [Output(display_name="Answer", name="answer", method="ask")]

    def ask(self) -> Message:
        card_id = str(self.card_id or "").strip()
        is_recheck = bool(card_id)
        options = sc.parse_options(self.options)

        if not is_recheck and not options:
            self.status = "No options given; nothing to ask."
            return Message(text=self.status)

        # Only meaningful if `options` was supplied this call (always true
        # on a fresh post; on a re-check it is whatever the caller happened
        # to pass again, or blank -- see the `options` field's own info
        # text). This is used ONLY to turn a matched tap's raw `action_id`
        # into a human-readable label; it never decides WHETHER a tap
        # counts as an answer (any tap on this card by a real, non-agent
        # chat member does -- see the matching loop below), so a re-check
        # with blank options still resolves correctly, just with the raw
        # `action_id` as the answer instead of its label.
        label_by_action = {f"opt_{i}": label for i, label in enumerate(options)}

        client = sc.get_client(self.host)
        try:
            if not is_recheck:
                blocks = sc.build_question_card(self.question, options)
                card = client.post_card(self.api_key, self.chat_id, blocks, self.question)
                card_id = sc.card_id_from_post(card)
                if not card_id:
                    self.status = "Salt did not return a card id; cannot match the answer."
                    return Message(text=self.status)

            try:
                card = sc.get_card(client, self.api_key, card_id)
            except SaltApiError as exc:
                # A 429 here is Salt's own rate limit, not "nobody has
                # answered" -- report it as a pending result with a hint
                # rather than raising, since the natural response (an
                # Agent-driven flow, or a scheduled re-run, re-invoking
                # this same component with the same card_id shortly) is
                # exactly the same action a real "no tap yet" result asks
                # for. Any other status still raises normally -- this is
                # the one status this single-shot check treats as
                # "try again", not "something is actually wrong".
                if exc.status == HTTP_TOO_MANY_REQUESTS:
                    wait = f"{exc.retry_after}s" if exc.retry_after else "a moment"
                    self.status = (
                        f"Rate limited by Salt; wait {wait} and re-run this component with "
                        f"card_id={card_id!r} to check again."
                    )
                    return Message(text=f"pending:{card_id}")
                raise
            interactions = card.get("interactions") or []  # newest first

            # Chat members, fetched only if there is at least one
            # interaction worth classifying -- this is what tells a real
            # human's tap apart from another agent's (or a since-removed
            # member's): the card's own interaction log
            # (`CardInteraction#as_json_for_owner`) carries only
            # `user_id`, never `account_type` or a username, unlike the
            # old outbox event body, which carried a full `user` object
            # inline. Skipping this call entirely on the (common) empty
            # case avoids paying for it when there is nothing to check yet.
            members_by_id: dict[str, dict[str, Any]] = {}
            if interactions:
                members_by_id = {
                    str(m.get("id", "")).lower(): m for m in client.get_chat_members(self.api_key, self.chat_id)
                }
        finally:
            client.close()

        match: tuple[dict[str, Any], dict[str, Any]] | None = None
        for interaction in interactions:
            tapper = members_by_id.get(str(interaction.get("user_id") or "").lower())
            # A tap from another agent, or from someone no longer a member
            # of this chat, never resolves a pending HUMAN ask. (Unlike
            # the old outbox-based design, we don't also check the tap's
            # own `card_id` here -- reading THIS card's own interaction
            # endpoint already scopes every row to this card.)
            if tapper is None or str(tapper.get("account_type") or "").lower() == "agent":
                continue
            match = (interaction, tapper)
            break  # newest-first: the first valid match is the most recent answer

        if match is None:
            prefix = "Posted" if not is_recheck else "Still"
            self.status = (
                f"{prefix}; no tap yet. Re-run this component with card_id={card_id!r} to check again, "
                "or see README for wiring up push via a webhook receiver."
            )
            return Message(text=f"pending:{card_id}")

        interaction, tapper = match
        action_id = str(interaction.get("action_id") or "")
        answer_label = label_by_action.get(action_id, action_id)
        answered_by = tapper.get("username") or tapper.get("id") or "someone"
        self.status = f"{answered_by} tapped {answer_label!r}."
        return Message(text=answer_label)
