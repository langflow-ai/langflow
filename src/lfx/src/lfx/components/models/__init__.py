"""Genesis Studio Autonomize Models Components."""

# Unified Autonomize Model Components
from .autonomize_model import AutonomizeModelComponent
from .autonomize_document_model import AutonomizeDocumentModelComponent

# Keep Form Recognizer as separate Azure OCR component
from .form_recognizer import FormRecognizerComponent

__all__ = [
    'AutonomizeModelComponent',
    'AutonomizeDocumentModelComponent',
    'FormRecognizerComponent'
]
