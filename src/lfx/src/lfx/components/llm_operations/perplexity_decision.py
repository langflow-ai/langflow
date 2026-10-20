from lfx.base.models.decisions.component import DecisionComponent


class PerplexityDecisionComponent(DecisionComponent):
    display_name = "Perplexity Decision Model"
    description = "Evaluate a choice, Boolean probability, or ordered score with Perplexity Decider."
    name = "PerplexityDecision"
    icon = "Perplexity"
    provider = "Perplexity"
