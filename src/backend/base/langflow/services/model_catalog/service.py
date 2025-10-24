"""
Model Catalog Service for AI Studio - AUTPE-6205.

This service provides a comprehensive catalog of all available models,
including Autonomize models and their variants, for use in agent specification building.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from langflow.services.base import Service
from langflow.services.modelhub.model_endpoint import ModelEndpoint

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a model."""

    id: str
    name: str
    display_name: str
    type: str  # text, document, embedding, etc.
    category: str  # healthcare, general, vision, etc.
    provider: str  # autonomize, openai, anthropic, etc.
    description: str

    # Input/Output specifications
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    supported_formats: List[str] = field(default_factory=list)

    # Model capabilities
    capabilities: Dict[str, Any] = field(default_factory=dict)

    # Healthcare compliance (optional)
    healthcare_metadata: Optional[Dict[str, Any]] = None

    # Configuration options
    config_options: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    beta: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class ModelCatalogService(Service):
    """Service for managing the model catalog."""

    name = "model_catalog_service"

    def __init__(self):
        """Initialize the model catalog service."""
        super().__init__()
        self._models: Dict[str, ModelInfo] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the model catalog with all available models."""
        if self._initialized:
            return

        logger.info("Initializing model catalog...")

        # Register Autonomize text models
        self._register_autonomize_text_models()

        # Register Autonomize document models
        self._register_autonomize_document_models()

        # Register other provider models (placeholder for future)
        self._register_other_models()

        self._initialized = True
        logger.info(f"Model catalog initialized with {len(self._models)} models")

    def _register_autonomize_text_models(self) -> None:
        """Register all Autonomize text-based models."""

        text_models = [
            ModelInfo(
                id="autonomize-clinical-llm",
                name="clinical_llm",
                display_name="Clinical LLM",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Extract clinical entities from medical text using advanced NLP",
                input_types=["text", "string"],
                output_types=["json", "entities"],
                capabilities={
                    "entity_extraction": True,
                    "clinical_nlp": True,
                    "hipaa_compliant": True,
                    "batch_processing": True
                },
                healthcare_metadata={
                    "hipaa_compliant": True,
                    "phi_handling": True,
                    "clinical_standards": ["HL7", "FHIR"],
                    "supported_entities": ["diagnoses", "medications", "procedures", "symptoms"]
                },
                config_options={
                    "confidence_threshold": 0.7,
                    "include_metadata": True,
                    "max_tokens": 4096
                }
            ),
            ModelInfo(
                id="autonomize-clinical-note-classifier",
                name="clinical_note_classifier",
                display_name="Clinical Note Classifier",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Classify clinical notes by type and specialty",
                input_types=["text", "string"],
                output_types=["classification", "json"],
                capabilities={
                    "document_classification": True,
                    "multi_label": True,
                    "confidence_scores": True
                },
                healthcare_metadata={
                    "hipaa_compliant": True,
                    "note_types": ["progress_note", "discharge_summary", "consultation", "operative_note"],
                    "specialties": ["cardiology", "oncology", "radiology", "pathology"]
                }
            ),
            ModelInfo(
                id="autonomize-combined-entity-linking",
                name="combined_entity_linking",
                display_name="Combined Entity Linking",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Link extracted entities to standard medical vocabularies",
                input_types=["text", "entities"],
                output_types=["linked_entities", "json"],
                capabilities={
                    "entity_linking": True,
                    "vocabulary_mapping": True,
                    "disambiguation": True
                },
                healthcare_metadata={
                    "supported_vocabularies": ["UMLS", "SNOMED-CT", "ICD-10", "RxNorm", "LOINC"],
                    "linking_confidence": True
                }
            ),
            ModelInfo(
                id="autonomize-cpt-code",
                name="cpt_code",
                display_name="CPT Code Extractor",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Extract CPT procedure codes from medical text",
                input_types=["text", "string"],
                output_types=["codes", "json"],
                capabilities={
                    "code_extraction": True,
                    "procedure_identification": True,
                    "billing_support": True
                },
                healthcare_metadata={
                    "code_system": "CPT",
                    "version": "2024",
                    "includes_modifiers": True
                }
            ),
            ModelInfo(
                id="autonomize-icd10-code",
                name="icd10_code",
                display_name="ICD-10 Code Extractor",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Extract ICD-10 diagnosis codes from medical text",
                input_types=["text", "string"],
                output_types=["codes", "json"],
                capabilities={
                    "diagnosis_coding": True,
                    "code_extraction": True,
                    "clinical_documentation": True
                },
                healthcare_metadata={
                    "code_system": "ICD-10-CM",
                    "version": "2024",
                    "includes_laterality": True,
                    "includes_severity": True
                }
            ),
            ModelInfo(
                id="autonomize-rxnorm-code",
                name="rxnorm_code",
                display_name="RxNorm Code Extractor",
                type="text",
                category="healthcare",
                provider="autonomize",
                description="Extract RxNorm medication codes from medical text",
                input_types=["text", "string"],
                output_types=["codes", "json"],
                capabilities={
                    "medication_extraction": True,
                    "drug_normalization": True,
                    "dosage_parsing": True
                },
                healthcare_metadata={
                    "code_system": "RxNorm",
                    "includes_generics": True,
                    "includes_brands": True,
                    "dosage_forms": True
                }
            )
        ]

        for model in text_models:
            self._models[model.id] = model
            logger.debug(f"Registered text model: {model.display_name}")

    def _register_autonomize_document_models(self) -> None:
        """Register all Autonomize document/image-based models."""

        document_models = [
            ModelInfo(
                id="autonomize-srf-extraction",
                name="srf_extraction",
                display_name="SRF Extraction",
                type="document",
                category="healthcare",
                provider="autonomize",
                description="Extract structured retinal findings from OCT images",
                input_types=["image", "file"],
                output_types=["findings", "json"],
                supported_formats=["jpg", "jpeg", "png", "tiff", "dicom"],
                capabilities={
                    "image_analysis": True,
                    "oct_processing": True,
                    "finding_extraction": True,
                    "measurement_extraction": True
                },
                healthcare_metadata={
                    "modality": "OCT",
                    "specialty": "ophthalmology",
                    "findings": ["SRF", "IRF", "PED", "CNV"],
                    "measurements": ["thickness", "volume", "area"]
                }
            ),
            ModelInfo(
                id="autonomize-srf-identification",
                name="srf_identification",
                display_name="SRF Identification",
                type="document",
                category="healthcare",
                provider="autonomize",
                description="Identify and classify subretinal fluid in retinal images",
                input_types=["image", "file"],
                output_types=["classification", "json"],
                supported_formats=["jpg", "jpeg", "png", "tiff", "dicom"],
                capabilities={
                    "image_classification": True,
                    "fluid_detection": True,
                    "severity_grading": True
                },
                healthcare_metadata={
                    "modality": "OCT",
                    "specialty": "ophthalmology",
                    "detection_types": ["presence", "location", "severity"],
                    "confidence_scoring": True
                }
            ),
            ModelInfo(
                id="autonomize-letter-split",
                name="letter_split",
                display_name="Letter Split Model",
                type="document",
                category="healthcare",
                provider="autonomize",
                description="Split and segment medical documents into logical sections",
                input_types=["document", "file"],
                output_types=["segments", "json"],
                supported_formats=["pdf", "jpg", "jpeg", "png", "tiff"],
                capabilities={
                    "document_segmentation": True,
                    "section_extraction": True,
                    "layout_analysis": True,
                    "text_extraction": True
                },
                healthcare_metadata={
                    "document_types": ["referral_letter", "discharge_summary", "consultation_note"],
                    "section_types": ["header", "history", "findings", "plan", "signature"],
                    "preserves_formatting": True
                }
            )
        ]

        for model in document_models:
            self._models[model.id] = model
            logger.debug(f"Registered document model: {model.display_name}")

    def _register_other_models(self) -> None:
        """Register models from other providers (placeholder for future expansion)."""
        # This will be expanded to include OpenAI, Anthropic, etc.
        pass

    def get_all_models(self,
                       filter_by_type: Optional[str] = None,
                       filter_by_category: Optional[str] = None,
                       filter_by_provider: Optional[str] = None,
                       active_only: bool = True) -> List[ModelInfo]:
        """Get all models with optional filtering."""

        if not self._initialized:
            self.initialize()

        models = list(self._models.values())

        # Apply filters
        if active_only:
            models = [m for m in models if m.active]

        if filter_by_type:
            models = [m for m in models if m.type == filter_by_type]

        if filter_by_category:
            models = [m for m in models if m.category == filter_by_category]

        if filter_by_provider:
            models = [m for m in models if m.provider == filter_by_provider]

        return models

    def get_model_by_id(self, model_id: str) -> Optional[ModelInfo]:
        """Get a specific model by ID."""

        if not self._initialized:
            self.initialize()

        return self._models.get(model_id)

    def search_models(self, query: str) -> List[ModelInfo]:
        """Search models by name or description."""

        if not self._initialized:
            self.initialize()

        query_lower = query.lower()
        results = []

        for model in self._models.values():
            if (query_lower in model.name.lower() or
                query_lower in model.display_name.lower() or
                query_lower in model.description.lower()):
                results.append(model)

        return results

    def get_models_by_capability(self, capability: str) -> List[ModelInfo]:
        """Get models that have a specific capability."""

        if not self._initialized:
            self.initialize()

        return [
            model for model in self._models.values()
            if capability in model.capabilities and model.capabilities[capability]
        ]

    def get_healthcare_compliant_models(self) -> List[ModelInfo]:
        """Get all HIPAA-compliant healthcare models."""

        if not self._initialized:
            self.initialize()

        return [
            model for model in self._models.values()
            if model.healthcare_metadata and
            model.healthcare_metadata.get("hipaa_compliant", False)
        ]

    def get_catalog_statistics(self) -> Dict[str, Any]:
        """Get statistics about the model catalog."""

        if not self._initialized:
            self.initialize()

        stats = {
            "total_models": len(self._models),
            "by_type": {},
            "by_category": {},
            "by_provider": {},
            "healthcare_compliant": 0,
            "active": 0,
            "beta": 0
        }

        for model in self._models.values():
            # Count by type
            if model.type not in stats["by_type"]:
                stats["by_type"][model.type] = 0
            stats["by_type"][model.type] += 1

            # Count by category
            if model.category not in stats["by_category"]:
                stats["by_category"][model.category] = 0
            stats["by_category"][model.category] += 1

            # Count by provider
            if model.provider not in stats["by_provider"]:
                stats["by_provider"][model.provider] = 0
            stats["by_provider"][model.provider] += 1

            # Count other attributes
            if model.healthcare_metadata and model.healthcare_metadata.get("hipaa_compliant"):
                stats["healthcare_compliant"] += 1

            if model.active:
                stats["active"] += 1

            if model.beta:
                stats["beta"] += 1

        return stats

    def export_catalog(self) -> Dict[str, Any]:
        """Export the entire catalog as a dictionary."""

        if not self._initialized:
            self.initialize()

        return {
            "models": [model.to_dict() for model in self._models.values()],
            "statistics": self.get_catalog_statistics(),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }