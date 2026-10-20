from lfx.base.models.decisions.component import DecisionComponent


class OpenAIDecisionComponent(DecisionComponent):
    display_name = "OpenAI Decision Model"
    description = "Evaluate a choice, Boolean probability, or ordered score with OpenAI Decisions."
    name = "OpenAIDecision"
    icon = "OpenAI"
    provider = "OpenAI"
