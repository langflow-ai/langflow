# API Healthcare Examples Guide

Comprehensive examples for using Genesis Agent API endpoints with healthcare specifications, connectors, and workflows.

## Overview

This guide provides detailed examples of using the Genesis Agent API endpoints with healthcare-specific specifications. It covers specification validation, workflow conversion, and healthcare system integration patterns.

## Healthcare API Endpoints

### Core Healthcare API Endpoints

- **POST** `/api/v1/spec/validate` - Validate healthcare specifications
- **POST** `/api/v1/spec/convert` - Convert healthcare specs to Langflow
- **GET** `/api/v1/spec/components` - List available healthcare components
- **POST** `/api/v1/workflows/healthcare` - Execute healthcare workflows
- **GET** `/api/v1/healthcare/connectors` - List healthcare connector status

## Specification Validation Examples

### Basic Healthcare Specification Validation

```bash
curl -X POST "http://localhost:7860/api/v1/spec/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "spec_yaml": "name: EHR Patient Data Processor\ndescription: Process patient data from EHR systems with HIPAA compliance\nversion: \"1.0.0\"\nagentGoal: Securely process patient health information from EHR systems\n\n# HIPAA compliance metadata\ndomain: autonomize.ai\nsubDomain: healthcare-ehr-integration\ntargetUser: internal\nvalueGeneration: ProcessAutomation\nsecurityInfo:\n  visibility: Private\n  confidentiality: High\n  gdprSensitive: true\n\ncomponents:\n  - id: patient-input\n    type: genesis:chat_input\n    name: Patient Data Input\n    description: Accept patient ID or search criteria\n    provides:\n      - in: ehr-agent\n        useAs: input\n        description: Send patient query to EHR agent\n\n  - id: ehr-connector\n    type: genesis:ehr_connector\n    name: Epic EHR Integration\n    description: Retrieve patient data from Epic EHR system\n    asTools: true\n    config:\n      ehr_system: epic\n      fhir_version: R4\n      authentication_type: oauth2\n      base_url: \"${EHR_BASE_URL}\"\n      operation: get_patient_data\n    provides:\n      - useAs: tools\n        in: ehr-agent\n        description: EHR data access capability\n\n  - id: ehr-agent\n    type: genesis:agent\n    name: EHR Processing Agent\n    description: Process patient data with HIPAA compliance\n    config:\n      system_prompt: \"You are a HIPAA-compliant EHR data processor. Always protect PHI and provide de-identified clinical summaries.\"\n      temperature: 0.1\n      max_tokens: 2000\n      handle_parsing_errors: true\n    provides:\n      - in: clinical-output\n        useAs: input\n        description: Send processed clinical data\n\n  - id: clinical-output\n    type: genesis:chat_output\n    name: Clinical Summary\n    description: Display de-identified clinical information"
  }'
```

**Response Example:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "healthcare_compliance": {
    "hipaa_compliant": true,
    "phi_protection": true,
    "security_metadata": true,
    "healthcare_components": ["genesis:ehr_connector"]
  },
  "validation_details": {
    "components_validated": 4,
    "connections_validated": 3,
    "healthcare_connectors": 1,
    "compliance_score": 100
  }
}
```

### Multi-Connector Healthcare Validation

```bash
curl -X POST "http://localhost:7860/api/v1/spec/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "spec_yaml": "name: Comprehensive Healthcare Workflow\ndescription: End-to-end healthcare workflow with multiple system integrations\nversion: \"1.0.0\"\nagentGoal: Orchestrate complete healthcare workflow from patient data to billing\n\n# Enterprise healthcare metadata\ndomain: autonomize.ai\nsubDomain: healthcare-orchestration\nkind: Single Agent\ntargetUser: internal\nvalueGeneration: ProcessAutomation\ntoolsUse: true\n\n# HIPAA compliance\nsecurityInfo:\n  visibility: Private\n  confidentiality: High\n  gdprSensitive: true\n\ncomponents:\n  - id: patient-input\n    type: genesis:chat_input\n    name: Patient Workflow Input\n    description: Accept patient information for comprehensive processing\n    provides:\n      - in: orchestration-agent\n        useAs: input\n        description: Send patient data to orchestration agent\n\n  - id: ehr-system\n    type: genesis:ehr_connector\n    name: EHR Integration\n    description: Electronic health record system access\n    asTools: true\n    config:\n      ehr_system: epic\n      fhir_version: R4\n      authentication_type: oauth2\n      base_url: \"${EHR_BASE_URL}\"\n      operation: get_patient_data\n    provides:\n      - useAs: tools\n        in: orchestration-agent\n        description: EHR data access capability\n\n  - id: eligibility-system\n    type: genesis:eligibility_connector\n    name: Insurance Eligibility\n    description: Real-time insurance eligibility verification\n    asTools: true\n    config:\n      eligibility_service: availity\n      provider_npi: \"${PROVIDER_NPI}\"\n      real_time_mode: true\n      cache_duration_minutes: 15\n      operation: verify_eligibility\n    provides:\n      - useAs: tools\n        in: orchestration-agent\n        description: Eligibility verification capability\n\n  - id: claims-system\n    type: genesis:claims_connector\n    name: Claims Processing\n    description: Healthcare claims and prior authorization system\n    asTools: true\n    config:\n      clearinghouse: change_healthcare\n      provider_npi: \"${PROVIDER_NPI}\"\n      test_mode: false\n      operation: submit_claim\n    provides:\n      - useAs: tools\n        in: orchestration-agent\n        description: Claims processing capability\n\n  - id: pharmacy-system\n    type: genesis:pharmacy_connector\n    name: Pharmacy Integration\n    description: E-prescribing and medication management\n    asTools: true\n    config:\n      pharmacy_network: surescripts\n      prescriber_npi: \"${PRESCRIBER_NPI}\"\n      interaction_checking: true\n      formulary_checking: true\n      operation: send_prescription\n    provides:\n      - useAs: tools\n        in: orchestration-agent\n        description: Pharmacy and medication tools\n\n  - id: orchestration-agent\n    type: genesis:agent\n    name: Healthcare Orchestration Agent\n    description: Orchestrates comprehensive healthcare workflow\n    config:\n      agent_llm: Azure OpenAI\n      model_name: gpt-4\n      temperature: 0.1\n      max_tokens: 4000\n      handle_parsing_errors: true\n      max_iterations: 12\n      verbose: false\n    provides:\n      - in: healthcare-output\n        useAs: input\n        description: Send comprehensive healthcare results\n\n  - id: healthcare-output\n    type: genesis:chat_output\n    name: Healthcare Workflow Results\n    description: Comprehensive healthcare workflow results\n    config:\n      should_store_message: true\n\n# Healthcare KPIs\nkpis:\n  - name: Workflow Completion Rate\n    category: Quality\n    valueType: percentage\n    target: 95\n    unit: '%'\n    description: Percentage of healthcare workflows completed successfully\n\n  - name: HIPAA Compliance Score\n    category: Security\n    valueType: percentage\n    target: 100\n    unit: '%'\n    description: HIPAA compliance rating for data handling"
  }'
```

**Response Example:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Consider adding clinical guidelines search for evidence-based recommendations"
  ],
  "healthcare_compliance": {
    "hipaa_compliant": true,
    "phi_protection": true,
    "security_metadata": true,
    "healthcare_components": [
      "genesis:ehr_connector",
      "genesis:eligibility_connector",
      "genesis:claims_connector",
      "genesis:pharmacy_connector"
    ],
    "multi_connector_workflow": true
  },
  "validation_details": {
    "components_validated": 7,
    "connections_validated": 6,
    "healthcare_connectors": 4,
    "compliance_score": 98,
    "performance_score": 85
  },
  "recommendations": [
    "Add genesis:knowledge_hub_search for clinical guidelines",
    "Consider adding audit logging configuration",
    "Implement error handling for healthcare connector failures"
  ]
}
```

## Workflow Conversion Examples

### EHR Integration Conversion

```bash
curl -X POST "http://localhost:7860/api/v1/spec/convert" \
  -H "Content-Type: application/json" \
  -d '{
    "spec_yaml": "name: Clinical Decision Support Agent\ndescription: Evidence-based clinical decision support with EHR integration\nversion: \"1.0.0\"\nagentGoal: Provide evidence-based clinical recommendations using EHR data and guidelines\n\n# Clinical workflow metadata\ndomain: autonomize.ai\nsubDomain: clinical-decision-support\nkind: Single Agent\ntargetUser: internal\nvalueGeneration: InsightGeneration\nagencyLevel: KnowledgeDrivenWorkflow\ntoolsUse: true\n\n# HIPAA compliance\nsecurityInfo:\n  visibility: Private\n  confidentiality: High\n  gdprSensitive: true\n\ncomponents:\n  - id: clinical-query\n    type: genesis:chat_input\n    name: Clinical Query Input\n    description: Accept clinical questions and patient scenarios\n    provides:\n      - in: clinical-agent\n        useAs: input\n        description: Send clinical query to decision agent\n\n  - id: guideline-search\n    type: genesis:knowledge_hub_search\n    name: Clinical Guidelines Search\n    description: Search clinical guidelines and protocols\n    asTools: true\n    config:\n      search_scope: clinical_guidelines\n      max_results: 10\n      document_types: [\"LCD\", \"NCD\", \"clinical_protocols\"]\n    provides:\n      - useAs: tools\n        in: clinical-agent\n        description: Clinical guideline search capability\n\n  - id: patient-data\n    type: genesis:ehr_connector\n    name: Patient Data Access\n    description: Access patient clinical data from EHR\n    asTools: true\n    config:\n      ehr_system: epic\n      fhir_version: R4\n      authentication_type: oauth2\n      operation: get_patient_data\n    provides:\n      - useAs: tools\n        in: clinical-agent\n        description: Patient data access for clinical context\n\n  - id: clinical-agent\n    type: genesis:agent\n    name: Clinical Decision Agent\n    description: Evidence-based clinical decision support agent\n    config:\n      agent_llm: Azure OpenAI\n      model_name: gpt-4\n      temperature: 0.1\n      max_tokens: 3000\n      handle_parsing_errors: true\n      max_iterations: 8\n    provides:\n      - in: clinical-output\n        useAs: input\n        description: Send clinical recommendations\n\n  - id: clinical-output\n    type: genesis:chat_output\n    name: Clinical Recommendations\n    description: Evidence-based clinical recommendations and rationale\n    config:\n      should_store_message: true",
    "target_runtime": "langflow"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "langflow_spec": {
    "id": "clinical-decision-support",
    "name": "Clinical Decision Support Agent",
    "description": "Evidence-based clinical decision support with EHR integration",
    "data": {
      "nodes": [
        {
          "id": "clinical-query",
          "type": "ChatInput",
          "position": {"x": 100, "y": 100},
          "data": {
            "node": {
              "name": "Clinical Query Input",
              "description": "Accept clinical questions and patient scenarios"
            }
          }
        },
        {
          "id": "guideline-search",
          "type": "KnowledgeHubSearch",
          "position": {"x": 300, "y": 50},
          "data": {
            "node": {
              "name": "Clinical Guidelines Search",
              "search_scope": "clinical_guidelines",
              "max_results": 10,
              "document_types": ["LCD", "NCD", "clinical_protocols"]
            }
          }
        },
        {
          "id": "patient-data",
          "type": "EHRConnector",
          "position": {"x": 300, "y": 150},
          "data": {
            "node": {
              "name": "Patient Data Access",
              "ehr_system": "epic",
              "fhir_version": "R4",
              "authentication_type": "oauth2",
              "operation": "get_patient_data"
            }
          }
        },
        {
          "id": "clinical-agent",
          "type": "Agent",
          "position": {"x": 500, "y": 100},
          "data": {
            "node": {
              "name": "Clinical Decision Agent",
              "agent_llm": "Azure OpenAI",
              "model_name": "gpt-4",
              "temperature": 0.1,
              "max_tokens": 3000,
              "handle_parsing_errors": true,
              "max_iterations": 8
            }
          }
        },
        {
          "id": "clinical-output",
          "type": "ChatOutput",
          "position": {"x": 700, "y": 100},
          "data": {
            "node": {
              "name": "Clinical Recommendations",
              "should_store_message": true
            }
          }
        }
      ],
      "edges": [
        {
          "id": "clinical-query-to-agent",
          "source": "clinical-query",
          "target": "clinical-agent",
          "data": {"targetHandle": "input"}
        },
        {
          "id": "guidelines-to-agent",
          "source": "guideline-search",
          "target": "clinical-agent",
          "data": {"targetHandle": "tools"}
        },
        {
          "id": "ehr-to-agent",
          "source": "patient-data",
          "target": "clinical-agent",
          "data": {"targetHandle": "tools"}
        },
        {
          "id": "agent-to-output",
          "source": "clinical-agent",
          "target": "clinical-output",
          "data": {"targetHandle": "input"}
        }
      ]
    }
  },
  "conversion_metadata": {
    "healthcare_connectors_converted": 1,
    "tools_configured": 2,
    "hipaa_compliance_preserved": true,
    "clinical_workflow_optimized": true
  }
}
```

### Multi-Agent Healthcare Conversion

```bash
curl -X POST "http://localhost:7860/api/v1/spec/convert" \
  -H "Content-Type: application/json" \
  -d '{
    "spec_yaml": "name: Healthcare Team Workflow\ndescription: Multi-agent healthcare workflow with specialized team members\nversion: \"1.0.0\"\nagentGoal: Provide comprehensive healthcare services through specialized agent collaboration\n\n# Multi-agent metadata\nkind: Multi Agent\ndomain: autonomize.ai\nsubDomain: healthcare-multi-agent\ntargetUser: internal\nvalueGeneration: ProcessAutomation\nagencyLevel: CollaborativeWorkflow\ntoolsUse: true\n\n# HIPAA compliance\nsecurityInfo:\n  visibility: Private\n  confidentiality: High\n  gdprSensitive: true\n\ncomponents:\n  - id: patient-input\n    type: genesis:chat_input\n    name: Patient Care Request\n    description: Comprehensive patient care request input\n    provides:\n      - in: healthcare-crew\n        useAs: input\n        description: Send patient request to healthcare team\n\n  - id: healthcare-crew\n    type: genesis:sequential_crew\n    name: Healthcare Team Coordination\n    description: Coordinates sequential healthcare workflow\n    config:\n      process: sequential\n      verbose: true\n      memory: true\n      max_rpm: 100\n    provides:\n      - in: care-output\n        useAs: input\n        description: Send coordinated care results\n\n  - id: clinical-agent\n    type: genesis:crewai_agent\n    name: Clinical Assessment Specialist\n    description: Provides comprehensive clinical assessment and diagnosis\n    config:\n      role: \"Senior Clinical Assessment Specialist\"\n      goal: \"Conduct thorough clinical assessments and develop evidence-based treatment plans\"\n      backstory: \"You are an experienced clinical specialist with expertise in comprehensive patient assessment and evidence-based medicine.\"\n      memory: true\n      verbose: true\n      allow_delegation: false\n    provides:\n      - in: healthcare-crew\n        useAs: agents\n        description: Provide clinical assessment capability\n\n  - id: pharmacy-agent\n    type: genesis:crewai_agent\n    name: Medication Management Specialist\n    description: Handles medication review, interactions, and optimization\n    config:\n      role: \"Clinical Pharmacist and Medication Specialist\"\n      goal: \"Ensure safe and effective medication therapy through comprehensive drug management\"\n      backstory: \"You are a clinical pharmacist with specialized training in medication therapy management and drug interaction analysis.\"\n      memory: true\n      verbose: true\n      allow_delegation: false\n    provides:\n      - in: healthcare-crew\n        useAs: agents\n        description: Provide medication management capability\n\n  - id: ehr-system\n    type: genesis:ehr_connector\n    name: EHR Integration\n    description: Electronic health record system access\n    asTools: true\n    config:\n      ehr_system: epic\n      fhir_version: R4\n      authentication_type: oauth2\n      operation: get_patient_data\n    provides:\n      - in: clinical-agent\n        useAs: tools\n        description: EHR data access for clinical assessment\n\n  - id: pharmacy-system\n    type: genesis:pharmacy_connector\n    name: Pharmacy Integration\n    description: Medication management and e-prescribing\n    asTools: true\n    config:\n      pharmacy_network: surescripts\n      interaction_checking: true\n      formulary_checking: true\n      operation: check_interactions\n    provides:\n      - in: pharmacy-agent\n        useAs: tools\n        description: Pharmacy tools for medication management\n\n  - id: assessment-task\n    type: genesis:sequential_task\n    name: Clinical Assessment Task\n    description: Comprehensive clinical assessment and treatment planning\n    config:\n      description: \"Conduct comprehensive clinical assessment including patient history review, symptom analysis, and evidence-based treatment recommendations.\"\n      expected_output: \"Comprehensive clinical assessment report with treatment recommendations\"\n      agent: clinical-agent\n    provides:\n      - in: healthcare-crew\n        useAs: tasks\n        description: Clinical assessment task\n\n  - id: medication-task\n    type: genesis:sequential_task\n    name: Medication Management Task\n    description: Comprehensive medication review and optimization\n    config:\n      description: \"Perform comprehensive medication management including drug interaction checking, formulary verification, and therapy optimization.\"\n      expected_output: \"Medication management report with safety recommendations\"\n      agent: pharmacy-agent\n    provides:\n      - in: healthcare-crew\n        useAs: tasks\n        description: Medication management task\n\n  - id: care-output\n    type: genesis:chat_output\n    name: Comprehensive Care Plan\n    description: Complete healthcare team assessment and care plan\n    config:\n      should_store_message: true",
    "target_runtime": "langflow"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "langflow_spec": {
    "id": "healthcare-team-workflow",
    "name": "Healthcare Team Workflow",
    "description": "Multi-agent healthcare workflow with specialized team members",
    "data": {
      "nodes": [
        {
          "id": "patient-input",
          "type": "ChatInput",
          "position": {"x": 100, "y": 200}
        },
        {
          "id": "healthcare-crew",
          "type": "SequentialCrew",
          "position": {"x": 300, "y": 200},
          "data": {
            "node": {
              "process": "sequential",
              "verbose": true,
              "memory": true,
              "max_rpm": 100
            }
          }
        },
        {
          "id": "clinical-agent",
          "type": "CrewAIAgent",
          "position": {"x": 200, "y": 100},
          "data": {
            "node": {
              "role": "Senior Clinical Assessment Specialist",
              "goal": "Conduct thorough clinical assessments and develop evidence-based treatment plans",
              "backstory": "You are an experienced clinical specialist with expertise in comprehensive patient assessment and evidence-based medicine.",
              "memory": true,
              "verbose": true,
              "allow_delegation": false
            }
          }
        },
        {
          "id": "pharmacy-agent",
          "type": "CrewAIAgent",
          "position": {"x": 200, "y": 300},
          "data": {
            "node": {
              "role": "Clinical Pharmacist and Medication Specialist",
              "goal": "Ensure safe and effective medication therapy through comprehensive drug management",
              "memory": true,
              "verbose": true
            }
          }
        },
        {
          "id": "ehr-system",
          "type": "EHRConnector",
          "position": {"x": 50, "y": 100}
        },
        {
          "id": "pharmacy-system",
          "type": "PharmacyConnector",
          "position": {"x": 50, "y": 300}
        },
        {
          "id": "care-output",
          "type": "ChatOutput",
          "position": {"x": 500, "y": 200}
        }
      ],
      "edges": [
        {
          "id": "input-to-crew",
          "source": "patient-input",
          "target": "healthcare-crew"
        },
        {
          "id": "crew-to-output",
          "source": "healthcare-crew",
          "target": "care-output"
        },
        {
          "id": "clinical-to-crew",
          "source": "clinical-agent",
          "target": "healthcare-crew",
          "data": {"targetHandle": "agents"}
        },
        {
          "id": "pharmacy-to-crew",
          "source": "pharmacy-agent",
          "target": "healthcare-crew",
          "data": {"targetHandle": "agents"}
        },
        {
          "id": "ehr-to-clinical",
          "source": "ehr-system",
          "target": "clinical-agent",
          "data": {"targetHandle": "tools"}
        },
        {
          "id": "pharmacy-sys-to-agent",
          "source": "pharmacy-system",
          "target": "pharmacy-agent",
          "data": {"targetHandle": "tools"}
        }
      ]
    }
  },
  "conversion_metadata": {
    "multi_agent_workflow": true,
    "crewai_components": 3,
    "healthcare_connectors_converted": 2,
    "sequential_tasks": 2,
    "hipaa_compliance_preserved": true
  }
}
```

## Healthcare Component Status Examples

### Get Healthcare Connector Status

```bash
curl -X GET "http://localhost:7860/api/v1/healthcare/connectors" \
  -H "Content-Type: application/json"
```

**Response Example:**
```json
{
  "connectors": {
    "ehr_connector": {
      "status": "available",
      "supported_systems": ["epic", "cerner", "allscripts", "athenahealth"],
      "fhir_versions": ["R4", "STU3", "DSTU2"],
      "authentication_types": ["oauth2", "basic", "api_key"],
      "operations": [
        "search_patients",
        "get_patient_data",
        "get_observations",
        "get_medications",
        "get_conditions",
        "get_providers"
      ],
      "hipaa_compliant": true,
      "mock_mode_available": true
    },
    "claims_connector": {
      "status": "available",
      "supported_clearinghouses": ["change_healthcare", "availity", "relay_health"],
      "edi_transactions": ["837", "835", "276", "277"],
      "operations": [
        "submit_claim",
        "check_claim_status",
        "get_remittance",
        "prior_authorization"
      ],
      "hipaa_compliant": true,
      "test_mode_available": true
    },
    "eligibility_connector": {
      "status": "available",
      "supported_services": ["availity", "change_healthcare", "navinet"],
      "real_time_verification": true,
      "cache_support": true,
      "operations": [
        "verify_eligibility",
        "get_benefit_summary",
        "check_coverage",
        "validate_provider"
      ],
      "hipaa_compliant": true
    },
    "pharmacy_connector": {
      "status": "available",
      "supported_networks": ["surescripts", "ncpdp", "relay_health"],
      "interaction_checking": true,
      "formulary_checking": true,
      "operations": [
        "send_prescription",
        "check_interactions",
        "verify_formulary",
        "medication_history"
      ],
      "hipaa_compliant": true,
      "dea_compliance": true
    }
  },
  "system_status": {
    "overall_health": "healthy",
    "hipaa_compliance_active": true,
    "audit_logging_enabled": true,
    "encryption_status": "active",
    "last_health_check": "2024-01-16T10:30:00Z"
  }
}
```

### Get Available Healthcare Components

```bash
curl -X GET "http://localhost:7860/api/v1/spec/components?category=healthcare" \
  -H "Content-Type: application/json"
```

**Response Example:**
```json
{
  "components": {
    "genesis:ehr_connector": {
      "display_name": "EHR Connector",
      "description": "Electronic Health Record integration with FHIR R4 and HL7 support",
      "category": "Healthcare",
      "config_schema": {
        "ehr_system": {
          "type": "string",
          "enum": ["epic", "cerner", "allscripts", "athenahealth"],
          "required": true
        },
        "fhir_version": {
          "type": "string",
          "enum": ["R4", "STU3", "DSTU2"],
          "default": "R4"
        },
        "authentication_type": {
          "type": "string",
          "enum": ["oauth2", "basic", "api_key"],
          "default": "oauth2"
        },
        "operation": {
          "type": "string",
          "enum": ["search_patients", "get_patient_data", "get_observations", "get_medications"]
        }
      },
      "connection_types": ["tools"],
      "hipaa_compliant": true
    },
    "genesis:claims_connector": {
      "display_name": "Claims Connector",
      "description": "Healthcare claims processing integration supporting EDI transactions",
      "category": "Healthcare",
      "config_schema": {
        "clearinghouse": {
          "type": "string",
          "enum": ["change_healthcare", "availity", "relay_health"],
          "required": true
        },
        "operation": {
          "type": "string",
          "enum": ["submit_claim", "check_claim_status", "prior_authorization"]
        },
        "test_mode": {
          "type": "boolean",
          "default": true
        }
      },
      "connection_types": ["tools"],
      "hipaa_compliant": true
    },
    "genesis:eligibility_connector": {
      "display_name": "Eligibility Connector",
      "description": "Insurance eligibility verification and benefit determination",
      "category": "Healthcare",
      "config_schema": {
        "eligibility_service": {
          "type": "string",
          "enum": ["availity", "change_healthcare", "navinet"],
          "required": true
        },
        "real_time_mode": {
          "type": "boolean",
          "default": true
        },
        "cache_duration_minutes": {
          "type": "integer",
          "default": 15
        }
      },
      "connection_types": ["tools"],
      "hipaa_compliant": true
    },
    "genesis:pharmacy_connector": {
      "display_name": "Pharmacy Connector",
      "description": "Pharmacy and medication management with e-prescribing integration",
      "category": "Healthcare",
      "config_schema": {
        "pharmacy_network": {
          "type": "string",
          "enum": ["surescripts", "ncpdp", "relay_health"],
          "required": true
        },
        "interaction_checking": {
          "type": "boolean",
          "default": true
        },
        "formulary_checking": {
          "type": "boolean",
          "default": true
        }
      },
      "connection_types": ["tools"],
      "hipaa_compliant": true
    }
  }
}
```

## Healthcare Workflow Execution Examples

### Execute EHR Patient Lookup

```bash
curl -X POST "http://localhost:7860/api/v1/workflows/healthcare/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "ehr-patient-lookup",
    "input_data": {
      "patient_query": "Find patient with MRN: MRN123456789",
      "operation": "search_patients",
      "ehr_system": "epic"
    },
    "config": {
      "hipaa_mode": true,
      "audit_logging": true,
      "mock_mode": true
    }
  }'
```

**Response Example:**
```json
{
  "execution_id": "exec_789456123",
  "status": "completed",
  "result": {
    "patient_found": true,
    "patient_summary": {
      "patient_id": "PAT-001",
      "demographics": {
        "age_range": "40-50",
        "gender": "female",
        "region": "Northeast"
      },
      "clinical_summary": {
        "primary_conditions": ["Type 2 diabetes", "Hypertension"],
        "current_medications": 3,
        "recent_visits": 2,
        "care_team_size": 4
      }
    },
    "hipaa_compliance": {
      "phi_protected": true,
      "data_deidentified": true,
      "audit_logged": true
    }
  },
  "processing_time_ms": 1234,
  "audit_reference": "AUD-2024-001234"
}
```

### Execute Multi-Connector Healthcare Workflow

```bash
curl -X POST "http://localhost:7860/api/v1/workflows/healthcare/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "comprehensive-healthcare",
    "input_data": {
      "patient_id": "PAT123456",
      "requested_services": ["clinical_assessment", "medication_review", "eligibility_check", "prior_authorization"],
      "provider_npi": "1234567890"
    },
    "config": {
      "hipaa_mode": true,
      "audit_logging": true,
      "real_time_mode": true,
      "max_processing_time_minutes": 10
    }
  }'
```

**Response Example:**
```json
{
  "execution_id": "exec_456789123",
  "status": "completed",
  "workflow_results": {
    "clinical_assessment": {
      "status": "completed",
      "summary": "Comprehensive clinical assessment completed with evidence-based recommendations",
      "recommendations": 4,
      "risk_level": "moderate",
      "follow_up_required": true
    },
    "medication_review": {
      "status": "completed",
      "current_medications": 5,
      "interactions_found": 0,
      "formulary_compliant": true,
      "optimization_recommendations": 2
    },
    "eligibility_verification": {
      "status": "completed",
      "coverage_active": true,
      "benefits_verified": true,
      "copay_amount": 25.00,
      "deductible_remaining": 150.00
    },
    "prior_authorization": {
      "status": "submitted",
      "auth_request_id": "PA-789123456",
      "estimated_approval_time": "24-48 hours",
      "approval_probability": "high"
    }
  },
  "hipaa_compliance": {
    "phi_protected": true,
    "audit_trail_complete": true,
    "compliance_score": 100
  },
  "performance_metrics": {
    "total_processing_time_ms": 8567,
    "connector_response_times": {
      "ehr_connector": 1234,
      "pharmacy_connector": 2345,
      "eligibility_connector": 3456,
      "claims_connector": 1532
    }
  },
  "audit_reference": "AUD-2024-001235"
}
```

## Error Handling Examples

### Validation Error Response

```json
{
  "valid": false,
  "errors": [
    {
      "field": "components[1].config.ehr_system",
      "message": "Invalid EHR system 'invalid_system'. Must be one of: epic, cerner, allscripts, athenahealth",
      "code": "INVALID_ENUM_VALUE"
    },
    {
      "field": "securityInfo",
      "message": "HIPAA compliance metadata required for healthcare workflows handling PHI",
      "code": "MISSING_HIPAA_METADATA"
    }
  ],
  "warnings": [
    {
      "field": "components[2].config.test_mode",
      "message": "Test mode is recommended for development environments",
      "code": "DEVELOPMENT_RECOMMENDATION"
    }
  ],
  "healthcare_compliance": {
    "hipaa_compliant": false,
    "missing_requirements": ["securityInfo", "audit_logging"],
    "recommendations": ["Add HIPAA compliance metadata", "Enable audit logging"]
  }
}
```

### Runtime Error Response

```json
{
  "execution_id": "exec_error_123",
  "status": "failed",
  "error": {
    "type": "HEALTHCARE_CONNECTOR_ERROR",
    "message": "EHR connector authentication failed",
    "code": "EHR_AUTH_FAILURE",
    "details": {
      "connector": "ehr_connector",
      "ehr_system": "epic",
      "error_reason": "OAuth2 token expired",
      "recovery_action": "Refresh authentication token"
    }
  },
  "hipaa_compliance": {
    "error_logged_securely": true,
    "phi_exposure": false,
    "audit_reference": "AUD-ERROR-2024-001"
  },
  "timestamp": "2024-01-16T10:45:00Z"
}
```

## Authentication and Security Examples

### Healthcare API Authentication

```bash
# Authentication with HIPAA compliance headers
curl -X POST "http://localhost:7860/api/v1/spec/validate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${HEALTHCARE_API_TOKEN}" \
  -H "X-HIPAA-Compliant: true" \
  -H "X-Audit-User-ID: physician_001" \
  -H "X-Access-Purpose: clinical_decision_support" \
  -d '{
    "spec_yaml": "...",
    "compliance_level": "hipaa",
    "audit_required": true
  }'
```

### Secure Environment Configuration

```bash
# Environment variables for healthcare API access
export HEALTHCARE_API_TOKEN="hc_token_abc123xyz789"
export EHR_BASE_URL="https://sandbox-ehr.example.com/fhir"
export PROVIDER_NPI="1234567890"
export PRESCRIBER_NPI="0987654321"
export AUDIT_ENDPOINT="https://audit.healthcare.example.com/api/v1/logs"
export ENCRYPTION_KEY="AES256_encryption_key_abc123"

# HIPAA compliance flags
export HIPAA_COMPLIANCE_ENABLED="true"
export PHI_PROTECTION_LEVEL="high"
export AUDIT_LOGGING_REQUIRED="true"
```

## Best Practices for Healthcare APIs

### Request Headers

```bash
# Required headers for healthcare API requests
-H "Content-Type: application/json"
-H "Authorization: Bearer ${HEALTHCARE_API_TOKEN}"
-H "X-HIPAA-Compliant: true"
-H "X-Audit-User-ID: ${USER_ID}"
-H "X-Access-Purpose: ${ACCESS_PURPOSE}"
-H "X-Request-ID: ${UNIQUE_REQUEST_ID}"
```

### Response Validation

```javascript
// Validate healthcare API responses
function validateHealthcareResponse(response) {
  // Check HIPAA compliance
  if (!response.hipaa_compliance || !response.hipaa_compliance.phi_protected) {
    throw new Error('Response does not meet HIPAA compliance requirements');
  }

  // Verify audit logging
  if (!response.audit_reference) {
    throw new Error('Audit reference missing from healthcare response');
  }

  // Check for PHI exposure
  if (containsPHI(response.data)) {
    throw new Error('Response contains unprotected PHI data');
  }

  return response;
}
```

### Error Handling

```javascript
// Healthcare-specific error handling
function handleHealthcareError(error) {
  // Log error securely without PHI
  const sanitizedError = sanitizePHI(error);
  audit.log('healthcare_api_error', sanitizedError);

  // Return user-friendly error without exposing PHI
  if (error.code === 'EHR_AUTH_FAILURE') {
    return {
      message: 'Healthcare system authentication failed. Please contact IT support.',
      support_reference: error.audit_reference
    };
  }

  // Generic error for unknown issues
  return {
    message: 'Healthcare service temporarily unavailable. Please try again later.',
    support_reference: error.audit_reference
  };
}
```

## Testing and Development

### Mock Mode Examples

```bash
# Enable mock mode for development testing
curl -X POST "http://localhost:7860/api/v1/workflows/healthcare/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "ehr-integration-test",
    "input_data": {
      "patient_id": "TEST_PAT_001",
      "operation": "get_patient_data"
    },
    "config": {
      "mock_mode": true,
      "test_environment": true,
      "hipaa_simulation": true
    }
  }'
```

### Validation Testing

```bash
# Test healthcare specification validation
curl -X POST "http://localhost:7860/api/v1/spec/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "spec_yaml": "...",
    "validation_mode": "strict",
    "healthcare_compliance": true,
    "check_hipaa": true,
    "verify_connectors": true
  }'
```

## Support and Troubleshooting

### Common Issues and Solutions

1. **EHR Authentication Failures**
   - Verify OAuth2 credentials and token expiration
   - Check network connectivity to EHR systems
   - Ensure proper FHIR version compatibility

2. **HIPAA Compliance Validation Errors**
   - Add required securityInfo metadata
   - Enable audit logging configuration
   - Verify PHI protection measures

3. **Healthcare Connector Timeouts**
   - Increase timeout values for healthcare APIs
   - Check healthcare system availability
   - Implement retry logic for transient failures

4. **Mock Data Inconsistencies**
   - Verify mock templates are up to date
   - Check FHIR resource structure compliance
   - Ensure clinical terminology accuracy

For additional support, see the [Healthcare Integration Guide](healthcare-integration.md), [HIPAA Compliance Guide](hipaa-compliance.md), and [Clinical Workflow Guide](clinical-workflow.md).