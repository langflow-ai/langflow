"""lfx-slack: Slack Web API actions and Slack triggers on Langflow connections.

Distribution unit ``lfx-slack``.  At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py``, registers the
bundle's components under namespaced IDs such as
``ext:slack:SlackSearchComponent@official``, and loads
``components/slack/capabilities.v1.json`` as the ``slack`` integration
provider's capability manifest.

Every action runs on the Slack Web API through ``slack_sdk``; the executing
identity (connected user vs the app's bot user) is fixed per component and
enforced against the resolved connection before the first request.

The two trigger components (``Slack: On Message``, ``Slack: On Reaction``) are
declarations: Langflow receives their events through the Events API or Socket
Mode on the server side, and the nodes hand the event to the flow.
"""

from lfx_slack.components.slack import (
    SlackAddReactionComponent,
    SlackCanvasComponent,
    SlackListChannelMembersComponent,
    SlackOnMessageTriggerComponent,
    SlackOnReactionTriggerComponent,
    SlackPostAsAppComponent,
    SlackReadThreadComponent,
    SlackSearchComponent,
    SlackSendAsUserComponent,
)

__all__ = [
    "SlackAddReactionComponent",
    "SlackCanvasComponent",
    "SlackListChannelMembersComponent",
    "SlackOnMessageTriggerComponent",
    "SlackOnReactionTriggerComponent",
    "SlackPostAsAppComponent",
    "SlackReadThreadComponent",
    "SlackSearchComponent",
    "SlackSendAsUserComponent",
]
