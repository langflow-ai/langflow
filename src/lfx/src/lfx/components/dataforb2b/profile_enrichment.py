"""DataForB2B — Profile Enrichment component for Langflow.

Enrich a professional profile from a LinkedIn URL: full profile plus work
email, personal email and GitHub. Works as an email finder for lead enrichment.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._client import DataForB2BClient

ENRICH_FLAGS = ("enrich_profile", "enrich_work_email", "enrich_personal_email", "enrich_github")


class DataForB2BProfileEnrichmentComponent(Component):
    display_name = "Enrich LinkedIn Profile"
    description = (
        "Look up and enrich a professional profile from a LinkedIn URL using "
        "DataForB2B — returns the full profile (current role, experience, skills) "
        "plus work email, personal email and GitHub. An email finder for lead "
        "enrichment, contact enrichment, cold outreach and CRM."
    )
    documentation = "https://docs.dataforb2b.ai"
    icon = "DataForB2B"
    name = "DataForB2BProfileEnrichment"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DataForB2B API Key",
            required=True,
            info="Your DataForB2B API key (header api_key). Get one at https://app.dataforb2b.ai.",
        ),
        MessageTextInput(
            name="profile_identifier",
            display_name="Profile identifier",
            value="",
            tool_mode=True,
            info="LinkedIn profile URL (or profile id) to enrich.",
        ),
        BoolInput(
            name="enrich_profile",
            display_name="Full profile",
            value=True,
            info="Return the full LinkedIn profile (role, experience, skills).",
        ),
        BoolInput(
            name="enrich_work_email",
            display_name="Work email",
            value=False,
            info="Find the professional / work email.",
        ),
        BoolInput(
            name="enrich_personal_email",
            display_name="Personal email",
            value=False,
            info="Find the personal email.",
        ),
        BoolInput(
            name="enrich_github",
            display_name="GitHub",
            value=False,
            advanced=True,
            info="Find the GitHub profile.",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="enrich"),
    ]

    def enrich(self) -> Data:
        if not self.profile_identifier:
            msg = "'profile_identifier' is required."
            raise ValueError(msg)
        payload: dict = {"profile_identifier": self.profile_identifier}
        any_flag = False
        for flag in ENRICH_FLAGS:
            value = bool(getattr(self, flag, False))
            payload[flag] = value
            any_flag = any_flag or value
        if not any_flag:  # >=1 flag required by the API
            payload["enrich_profile"] = True

        data = DataForB2BClient(self.api_key).enrich_profile(payload)
        self.status = "Enriched"
        return Data(data=data)
