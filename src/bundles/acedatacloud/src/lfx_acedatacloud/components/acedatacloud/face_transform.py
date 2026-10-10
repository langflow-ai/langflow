"""Face Transform components."""

from lfx_acedatacloud.components.base import (
    AceGenerationComponent,
    generation_inputs,
)


class FaceTransformComponent(AceGenerationComponent):
    display_name = "Face Transform"
    description = "Run the Ace Data Cloud Face Transform first-run API action."
    icon = "Bot"
    service_name = "face_transform"
    inputs = generation_inputs("face_transform")
