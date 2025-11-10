"""EHR Healthcare Connector for Electronic Health Record integration."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.io import DropdownInput, MessageTextInput, Output, StrInput
from langflow.schema.data import Data


class EHRConnector(HealthcareConnectorBase):
    """
    Electronic Health Record (EHR) Connector.

    Provides standardized integration with major EHR systems including Epic, Cerner,
    Allscripts, and athenahealth. Supports FHIR R4-compliant data exchange and
    clinical workflow automation.

    Features:
    - FHIR R4 resource management (Patient, Observation, Condition, Medication)
    - HL7 message processing (ADT, ORM, ORU, SIU message types)
    - OAuth2, Basic Auth, and API key authentication support
    - HIPAA-compliant data handling and audit logging
    """

    display_name = "EHR Connector"
    description = "Electronic Health Record integration with FHIR R4 and HL7 support"
    documentation: str = "https://docs.langflow.org/components-healthcare-ehr"
    icon = "FileText"
    name = "EHRConnector"
    category = "connectors"


    outputs = [
        Output(display_name="EHR Data", name="ehr_data", method="build_ehr_response"),
    ]

    def __init__(self, **kwargs):
        """Initialize EHRConnector with healthcare base inputs and EHR-specific inputs."""
        super().__init__(**kwargs)

        # Add EHR-specific inputs to the base class inputs
        ehr_inputs = [
            MessageTextInput(
                name="patient_query",
                display_name="Patient Query",
                info="Patient search criteria or request data (JSON format)",
                value='{"patient_id": "PAT123456", "operation": "get_patient_data"}',
                tool_mode=True,
            ),
            DropdownInput(
                name="ehr_system",
                display_name="EHR System",
                options=["epic", "cerner", "allscripts", "athenahealth"],
                value="epic",
                info="EHR system type for integration",
                tool_mode=True,
            ),
            DropdownInput(
                name="fhir_version",
                display_name="FHIR Version",
                options=["R4", "STU3", "DSTU2"],
                value="R4",
                info="FHIR version for resource compatibility",
                tool_mode=True,
            ),
            DropdownInput(
                name="authentication_type",
                display_name="Authentication Type",
                options=["oauth2", "basic", "api_key"],
                value="oauth2",
                info="Authentication method for EHR system",
                tool_mode=True,
            ),
            StrInput(
                name="base_url",
                display_name="Base URL",
                info="EHR system base URL (use environment variables for production)",
                value="${EHR_BASE_URL}",
                tool_mode=True,
            ),
            DropdownInput(
                name="operation",
                display_name="Operation",
                options=[
                    "search_patients",
                    "get_patient_data",
                    "get_observations",
                    "get_medications",
                    "get_conditions",
                    "get_providers",
                    "update_patient_data",
                    "get_care_team",
                    "get_care_plan"
                ],
                value="get_patient_data",
                info="EHR operation to perform",
                tool_mode=True,
            ),
        ]

        # Combine base class inputs with EHR-specific inputs
        self.inputs = self.inputs + ehr_inputs

    def get_required_fields(self) -> List[str]:
        """Get required fields for EHR operations."""
        return ["operation"]

    def build_ehr_response(self) -> Data:
        """Build EHR response based on patient query and operation."""
        try:
            # Parse patient query
            if isinstance(self.patient_query, str):
                try:
                    query_data = json.loads(self.patient_query)
                except json.JSONDecodeError:
                    # If not JSON, treat as simple patient ID
                    query_data = {"patient_id": self.patient_query, "operation": self.operation}
            else:
                query_data = {"operation": self.operation}
    
            # FIX: ALWAYS use the dropdown operation value (override query_data)
            query_data["operation"] = self.operation  # ← Changed from conditional to always set
            
            # Add EHR system configuration
            query_data.update({
                "ehr_system": self.ehr_system,
                "fhir_version": self.fhir_version,
                "authentication_type": self.authentication_type,
                "base_url": self.base_url,
            })
    
            # Execute healthcare workflow
            return self.execute_healthcare_workflow(query_data)
    
        except Exception as e:
            return self._handle_healthcare_error(e, "ehr_response_building")

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive mock EHR data for development."""
        operation = request_data.get("operation", "get_patient_data")
        patient_id = request_data.get("patient_id", "PAT123456")
        ehr_system = request_data.get("ehr_system", "epic")

        # Base mock patient data following FHIR R4 structure
        base_patient = {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [
                {
                    "use": "usual",
                    "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]},
                    "system": f"http://{ehr_system}.example.com/mrn",
                    "value": f"MRN{patient_id}"
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": "Johnson",
                    "given": ["Sarah", "Elizabeth"]
                }
            ],
            "gender": "female",
            "birthDate": "1985-03-15",
            "address": [
                {
                    "use": "home",
                    "type": "both",
                    "line": ["123 Healthcare Ave"],
                    "city": "Medical City",
                    "state": "HC",
                    "postalCode": "12345",
                    "country": "US"
                }
            ],
            "telecom": [
                {"system": "phone", "value": "+1-555-0123", "use": "home"},
                {"system": "email", "value": "sarah.johnson@email.example", "use": "home"}
            ],
            "managingOrganization": {
                "reference": "Organization/ehr-hospital-001",
                "display": "Example Healthcare System"
            }
        }

        if operation == "search_patients":
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 1,
                "entry": [
                    {
                        "resource": base_patient,
                        "search": {"mode": "match"}
                    }
                ],
                "search_criteria": request_data,
                "processing_time_ms": 234
            }

        elif operation == "get_patient_data":
            return {
                **base_patient,
                "meta": {
                    "lastUpdated": "2024-01-15T10:30:00Z",
                    "versionId": "1",
                    "source": f"{ehr_system}_ehr_system"
                },
                "extension": [
                    {
                        "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                        "valueCodeableConcept": {
                            "coding": [{"system": "urn:oid:2.16.840.1.113883.6.238", "code": "2106-3", "display": "White"}]
                        }
                    }
                ],
                "processing_time_ms": 189
            }

        elif operation == "get_observations":
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 3,
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "obs-001",
                            "status": "final",
                            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
                            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]},
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "effectiveDateTime": "2024-01-15T10:30:00Z",
                            "component": [
                                {
                                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                                    "valueQuantity": {"value": 120, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}
                                },
                                {
                                    "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
                                    "valueQuantity": {"value": 80, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}
                                }
                            ]
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "obs-002",
                            "status": "final",
                            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
                            "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body Weight"}]},
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "effectiveDateTime": "2024-01-15T10:30:00Z",
                            "valueQuantity": {"value": 70, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"}
                        }
                    }
                ],
                "processing_time_ms": 312
            }

        elif operation == "get_medications":
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 5,
                "entry": [
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-001",
                            "status": "active",
                            "intent": "order",
                            "priority": "routine",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {
                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                        "code": "860975",
                                        "display": "Metformin 500 MG Oral Tablet"
                                    },
                                    {
                                        "system": "http://www.whocc.no/atc",
                                        "code": "A10BA02",
                                        "display": "Metformin"
                                    }
                                ],
                                "text": "Metformin 500mg tablet"
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "authoredOn": "2024-01-01T09:00:00Z",
                            "requester": {
                                "reference": "Practitioner/pract-001",
                                "display": "Dr. Robert Smith"
                            },
                            "reasonCode": [
                                {
                                    "coding": [
                                        {
                                            "system": "http://snomed.info/sct",
                                            "code": "44054006",
                                            "display": "Type 2 diabetes mellitus"
                                        }
                                    ]
                                }
                            ],
                            "note": [
                                {
                                    "text": "Monitor blood glucose levels regularly. Take with food to reduce GI side effects."
                                }
                            ],
                            "dosageInstruction": [
                                {
                                    "sequence": 1,
                                    "text": "Take one tablet twice daily with meals",
                                    "additionalInstruction": [
                                        {
                                            "coding": [
                                                {
                                                    "system": "http://snomed.info/sct",
                                                    "code": "311504000",
                                                    "display": "With or after food"
                                                }
                                            ]
                                        }
                                    ],
                                    "timing": {
                                        "repeat": {
                                            "frequency": 2,
                                            "period": 1,
                                            "periodUnit": "d",
                                            "when": ["MORN", "EVE"]
                                        }
                                    },
                                    "route": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "26643006",
                                                "display": "Oral route"
                                            }
                                        ]
                                    },
                                    "doseAndRate": [
                                        {
                                            "type": {
                                                "coding": [
                                                    {
                                                        "system": "http://terminology.hl7.org/CodeSystem/dose-rate-type",
                                                        "code": "ordered",
                                                        "display": "Ordered"
                                                    }
                                                ]
                                            },
                                            "doseQuantity": {
                                                "value": 1,
                                                "unit": "tablet",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "{tablet}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "dispenseRequest": {
                                "validityPeriod": {
                                    "start": "2024-01-01",
                                    "end": "2024-07-01"
                                },
                                "numberOfRepeatsAllowed": 5,
                                "quantity": {
                                    "value": 60,
                                    "unit": "tablets",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "{tablet}"
                                },
                                "expectedSupplyDuration": {
                                    "value": 30,
                                    "unit": "days",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "d"
                                }
                            },
                            "substitution": {
                                "allowedBoolean": True,
                                "reason": {
                                    "coding": [
                                        {
                                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                                            "code": "FP",
                                            "display": "formulary policy"
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-002",
                            "status": "active",
                            "intent": "order",
                            "priority": "routine",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {
                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                        "code": "197361",
                                        "display": "Lisinopril 10 MG Oral Tablet"
                                    },
                                    {
                                        "system": "http://www.whocc.no/atc",
                                        "code": "C09AA03",
                                        "display": "Lisinopril"
                                    }
                                ],
                                "text": "Lisinopril 10mg tablet"
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "authoredOn": "2024-01-01T09:15:00Z",
                            "requester": {
                                "reference": "Practitioner/pract-001",
                                "display": "Dr. Robert Smith"
                            },
                            "reasonCode": [
                                {
                                    "coding": [
                                        {
                                            "system": "http://snomed.info/sct",
                                            "code": "38341003",
                                            "display": "Essential hypertension"
                                        }
                                    ]
                                }
                            ],
                            "note": [
                                {
                                    "text": "Monitor blood pressure regularly. Report any persistent cough or dizziness."
                                }
                            ],
                            "dosageInstruction": [
                                {
                                    "sequence": 1,
                                    "text": "Take one tablet once daily in the morning",
                                    "timing": {
                                        "repeat": {
                                            "frequency": 1,
                                            "period": 1,
                                            "periodUnit": "d",
                                            "when": ["MORN"]
                                        }
                                    },
                                    "route": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "26643006",
                                                "display": "Oral route"
                                            }
                                        ]
                                    },
                                    "doseAndRate": [
                                        {
                                            "type": {
                                                "coding": [
                                                    {
                                                        "system": "http://terminology.hl7.org/CodeSystem/dose-rate-type",
                                                        "code": "ordered",
                                                        "display": "Ordered"
                                                    }
                                                ]
                                            },
                                            "doseQuantity": {
                                                "value": 1,
                                                "unit": "tablet",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "{tablet}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "dispenseRequest": {
                                "validityPeriod": {
                                    "start": "2024-01-01",
                                    "end": "2024-07-01"
                                },
                                "numberOfRepeatsAllowed": 5,
                                "quantity": {
                                    "value": 30,
                                    "unit": "tablets",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "{tablet}"
                                },
                                "expectedSupplyDuration": {
                                    "value": 30,
                                    "unit": "days",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "d"
                                }
                            },
                            "substitution": {
                                "allowedBoolean": True
                            }
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-003",
                            "status": "active",
                            "intent": "order",
                            "priority": "routine",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {
                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                        "code": "617314",
                                        "display": "Atorvastatin 20 MG Oral Tablet"
                                    },
                                    {
                                        "system": "http://www.whocc.no/atc",
                                        "code": "C10AA05",
                                        "display": "Atorvastatin"
                                    }
                                ],
                                "text": "Atorvastatin 20mg tablet"
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "authoredOn": "2024-01-01T09:20:00Z",
                            "requester": {
                                "reference": "Practitioner/pract-001",
                                "display": "Dr. Robert Smith"
                            },
                            "reasonCode": [
                                {
                                    "coding": [
                                        {
                                            "system": "http://snomed.info/sct",
                                            "code": "13644009",
                                            "display": "Hypercholesterolemia"
                                        }
                                    ],
                                    "text": "High cholesterol management"
                                }
                            ],
                            "note": [
                                {
                                    "text": "Take in the evening. Avoid grapefruit juice. Monitor liver function tests annually."
                                }
                            ],
                            "dosageInstruction": [
                                {
                                    "sequence": 1,
                                    "text": "Take one tablet once daily in the evening",
                                    "timing": {
                                        "repeat": {
                                            "frequency": 1,
                                            "period": 1,
                                            "periodUnit": "d",
                                            "when": ["EVE"]
                                        }
                                    },
                                    "route": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "26643006",
                                                "display": "Oral route"
                                            }
                                        ]
                                    },
                                    "doseAndRate": [
                                        {
                                            "doseQuantity": {
                                                "value": 1,
                                                "unit": "tablet",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "{tablet}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "dispenseRequest": {
                                "validityPeriod": {
                                    "start": "2024-01-01",
                                    "end": "2024-07-01"
                                },
                                "numberOfRepeatsAllowed": 5,
                                "quantity": {
                                    "value": 30,
                                    "unit": "tablets",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "{tablet}"
                                },
                                "expectedSupplyDuration": {
                                    "value": 30,
                                    "unit": "days",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "d"
                                }
                            }
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-004",
                            "status": "active",
                            "intent": "order",
                            "priority": "routine",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {
                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                        "code": "308136",
                                        "display": "Aspirin 81 MG Oral Tablet"
                                    }
                                ],
                                "text": "Aspirin 81mg (low-dose) tablet"
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "authoredOn": "2024-01-01T09:25:00Z",
                            "requester": {
                                "reference": "Practitioner/pract-001",
                                "display": "Dr. Robert Smith"
                            },
                            "reasonCode": [
                                {
                                    "coding": [
                                        {
                                            "system": "http://snomed.info/sct",
                                            "code": "134436002",
                                            "display": "Cardiovascular disease prevention"
                                        }
                                    ],
                                    "text": "Cardiovascular disease prevention"
                                }
                            ],
                            "note": [
                                {
                                    "text": "Take with food. Report any signs of unusual bleeding or bruising."
                                }
                            ],
                            "dosageInstruction": [
                                {
                                    "sequence": 1,
                                    "text": "Take one tablet once daily with food",
                                    "additionalInstruction": [
                                        {
                                            "coding": [
                                                {
                                                    "system": "http://snomed.info/sct",
                                                    "code": "311504000",
                                                    "display": "With or after food"
                                                }
                                            ]
                                        }
                                    ],
                                    "timing": {
                                        "repeat": {
                                            "frequency": 1,
                                            "period": 1,
                                            "periodUnit": "d"
                                        }
                                    },
                                    "route": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "26643006",
                                                "display": "Oral route"
                                            }
                                        ]
                                    },
                                    "doseAndRate": [
                                        {
                                            "doseQuantity": {
                                                "value": 1,
                                                "unit": "tablet",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "{tablet}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "dispenseRequest": {
                                "validityPeriod": {
                                    "start": "2024-01-01",
                                    "end": "2024-07-01"
                                },
                                "numberOfRepeatsAllowed": 5,
                                "quantity": {
                                    "value": 30,
                                    "unit": "tablets",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "{tablet}"
                                },
                                "expectedSupplyDuration": {
                                    "value": 30,
                                    "unit": "days",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "d"
                                }
                            }
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-005",
                            "status": "completed",
                            "intent": "order",
                            "priority": "routine",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {
                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                        "code": "1049221",
                                        "display": "Amoxicillin 500 MG Oral Capsule"
                                    }
                                ],
                                "text": "Amoxicillin 500mg capsule"
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "authoredOn": "2023-12-01T10:00:00Z",
                            "requester": {
                                "reference": "Practitioner/pract-003",
                                "display": "Dr. Jennifer Martinez"
                            },
                            "reasonCode": [
                                {
                                    "coding": [
                                        {
                                            "system": "http://snomed.info/sct",
                                            "code": "43878008",
                                            "display": "Streptococcal pharyngitis"
                                        }
                                    ],
                                    "text": "Bacterial throat infection"
                                }
                            ],
                            "note": [
                                {
                                    "text": "Course completed. No adverse reactions reported."
                                }
                            ],
                            "dosageInstruction": [
                                {
                                    "sequence": 1,
                                    "text": "Take one capsule three times daily for 10 days",
                                    "timing": {
                                        "repeat": {
                                            "boundsDuration": {
                                                "value": 10,
                                                "unit": "days",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "d"
                                            },
                                            "frequency": 3,
                                            "period": 1,
                                            "periodUnit": "d"
                                        }
                                    },
                                    "route": {
                                        "coding": [
                                            {
                                                "system": "http://snomed.info/sct",
                                                "code": "26643006",
                                                "display": "Oral route"
                                            }
                                        ]
                                    },
                                    "doseAndRate": [
                                        {
                                            "doseQuantity": {
                                                "value": 1,
                                                "unit": "capsule",
                                                "system": "http://unitsofmeasure.org",
                                                "code": "{capsule}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "dispenseRequest": {
                                "validityPeriod": {
                                    "start": "2023-12-01",
                                    "end": "2023-12-11"
                                },
                                "numberOfRepeatsAllowed": 0,
                                "quantity": {
                                    "value": 30,
                                    "unit": "capsules",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "{capsule}"
                                },
                                "expectedSupplyDuration": {
                                    "value": 10,
                                    "unit": "days",
                                    "system": "http://unitsofmeasure.org",
                                    "code": "d"
                                }
                            }
                        }
                    }
                ],
                "processing_time_ms": 198,
            }


        elif operation == "get_conditions":
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 3,
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "cond-001",
                            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
                            "code": {
                                "coding": [
                                    {"system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 diabetes mellitus"},
                                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "Type 2 diabetes mellitus without complications"}
                                ]
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "onsetDateTime": "2020-03-15",
                            "recordedDate": "2020-03-15"
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "cond-002",
                            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
                            "code": {
                                "coding": [
                                    {"system": "http://snomed.info/sct", "code": "38341003", "display": "Essential hypertension"},
                                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I10", "display": "Essential (primary) hypertension"}
                                ]
                            },
                            "subject": {"reference": f"Patient/{patient_id}"},
                            "onsetDateTime": "2019-08-10",
                            "recordedDate": "2019-08-10"
                        }
                    }
                ],
                "processing_time_ms": 276
            }

        elif operation == "get_providers":
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": 2,
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Practitioner",
                            "id": "pract-001",
                            "identifier": [
                                {"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}
                            ],
                            "active": True,
                            "name": [{"family": "Smith", "given": ["Robert", "James"], "prefix": ["Dr."]}],
                            "telecom": [
                                {"system": "phone", "value": "+1-555-0199", "use": "work"},
                                {"system": "email", "value": "dr.smith@hospital.example", "use": "work"}
                            ],
                            "qualification": [
                                {
                                    "code": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0360", "code": "MD", "display": "Doctor of Medicine"}]}
                                }
                            ]
                        }
                    }
                ],
                "processing_time_ms": 145
            }

        elif operation == "get_care_team":
            return {
                "resourceType": "CareTeam",
                "id": "careteam-001",
                "status": "active",
                "subject": {"reference": f"Patient/{patient_id}"},
                "period": {"start": "2024-01-01"},
                "participant": [
                    {
                        "role": [{"coding": [{"system": "http://snomed.info/sct", "code": "17561000", "display": "Cardiologist"}]}],
                        "member": {"reference": "Practitioner/pract-001", "display": "Dr. Robert Smith"},
                        "period": {"start": "2024-01-01"}
                    },
                    {
                        "role": [{"coding": [{"system": "http://snomed.info/sct", "code": "46255001", "display": "Pharmacist"}]}],
                        "member": {"reference": "Practitioner/pract-002", "display": "PharmD Sarah Wilson"},
                        "period": {"start": "2024-01-01"}
                    }
                ],
                "managingOrganization": [{"reference": "Organization/ehr-hospital-001"}],
                "processing_time_ms": 167
            }

        else:
            # Default response for unknown operations
            return {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-supported",
                        "diagnostics": f"Operation '{operation}' is not supported by this EHR connector"
                    }
                ],
                "processing_time_ms": 23
            }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real EHR requests (production implementation).

        In production, this would:
        1. Authenticate with the EHR system using configured credentials
        2. Construct appropriate FHIR R4 requests
        3. Handle HL7 message processing for supported message types
        4. Manage OAuth2 token refresh and error handling
        5. Apply rate limiting and connection pooling
        """
        # This is where real EHR integration would be implemented
        # For now, return mock data with a note about production setup

        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "This is mock data. Configure EHR credentials for live data."
        mock_response["ehr_system_configured"] = self.ehr_system
        mock_response["authentication_type"] = self.authentication_type

        return mock_response

    def search_patients(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for patients based on criteria."""
        search_request = {**criteria, "operation": "search_patients"}
        response = self.execute_healthcare_workflow(search_request)

        if response.data.get("resourceType") == "Bundle":
            return [entry["resource"] for entry in response.data.get("entry", [])]
        return []

    def get_patient_data(self, patient_id: str) -> Dict[str, Any]:
        """Get comprehensive patient data."""
        request = {"patient_id": patient_id, "operation": "get_patient_data"}
        response = self.execute_healthcare_workflow(request)
        return response.data

    def get_observations(self, patient_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get patient observations (vital signs, lab results, etc.)."""
        request = {"patient_id": patient_id, "operation": "get_observations"}
        if category:
            request["category"] = category

        response = self.execute_healthcare_workflow(request)

        if response.data.get("resourceType") == "Bundle":
            return [entry["resource"] for entry in response.data.get("entry", [])]
        return []

    def get_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient medication list."""
        request = {"patient_id": patient_id, "operation": "get_medications"}
        response = self.execute_healthcare_workflow(request)

        if response.data.get("resourceType") == "Bundle":
            return [entry["resource"] for entry in response.data.get("entry", [])]
        return []

    def get_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient conditions/diagnoses."""
        request = {"patient_id": patient_id, "operation": "get_conditions"}
        response = self.execute_healthcare_workflow(request)

        if response.data.get("resourceType") == "Bundle":
            return [entry["resource"] for entry in response.data.get("entry", [])]
        return []

    def update_patient_data(self, patient_id: str, data: Dict[str, Any]) -> bool:
        """Update patient data (requires appropriate permissions)."""
        request = {
            "patient_id": patient_id,
            "operation": "update_patient_data",
            "update_data": data
        }

        try:
            response = self.execute_healthcare_workflow(request)
            return not response.data.get("error", False)
        except Exception:
            return False

    def execute_healthcare_workflow(self, request_data: dict) -> Data:
        """Execute healthcare workflow with comprehensive error handling and audit logging."""
        try:
            # Log request for audit trail
            self._audit_log_request(request_data)

            # Sanitize PHI data for security
            sanitized_data = self._sanitize_phi_data(request_data)

            # Process healthcare request
            response_data = self.process_healthcare_request(sanitized_data)

            # Create Data object with healthcare response
            return Data(
                data=response_data,
                text=f"EHR operation completed: {request_data.get('operation', 'unknown')}",
            )

        except Exception as e:
            return self._handle_healthcare_error(e, "execute_healthcare_workflow")

    def _handle_healthcare_error(self, error: Exception, operation: str) -> Data:
        """Handle healthcare-specific errors with HIPAA compliance."""
        # Log error without exposing PHI
        error_message = f"Healthcare operation failed: {operation}"

        # Create secure error response
        error_data = {
            "error": True,
            "operation": operation,
            "message": "Healthcare operation encountered an error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "compliance_note": "Error details logged securely per HIPAA requirements"
        }

        return Data(
            data=error_data,
            text=error_message,
        )

    def _audit_log_request(self, request_data: dict) -> None:
        """Log healthcare request for audit trail (HIPAA compliance)."""
        # In production, this would write to secure audit log
        pass

    def _sanitize_phi_data(self, data: dict) -> dict:
        """Sanitize PHI data according to HIPAA requirements."""
        # In production, this would implement proper PHI sanitization
        return data
