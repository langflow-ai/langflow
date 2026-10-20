from lfx.base.models.decisions.component import DecisionComponent


class TypeSafeDecisionComponent(DecisionComponent):
    display_name = "TypeSafe Decision Model"
    description = "Evaluate a choice, Boolean probability, or ordered score with TypeSafe Jev."
    name = "TypeSafeDecision"
    icon = "Split"
    provider = "TypeSafe"
