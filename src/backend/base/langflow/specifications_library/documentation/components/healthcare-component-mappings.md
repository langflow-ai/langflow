# Healthcare Component Mappings for Enhanced Decision Framework

## Overview

This document provides comprehensive mappings for healthcare-specific components introduced as part of AUTPE-6190 "Enhanced Decision Framework for AI Services and Healthcare Components". These mappings support the improved component type selection guidelines and ensure proper integration with AI Studio.

## New Healthcare Component Types

### Autonomize AI Models

#### autonomize:icd10_code_model
**Purpose**: Specialized AI model for ICD-10-CM and ICD-10-PCS medical coding

**Component Mapping**:
```python
"autonomize:icd10_code_model": {
    "component": "AutonomizeModel",
    "config": {"selected_model": "ICD-10 Code"},
    "dataType": "AutonomizeModel"
}
```

**Configuration Options**:
```yaml
config:
  selected_model: "ICD-10 Code"      # Required: Model selection
  confidence_threshold: 0.85          # Optional: Minimum confidence (0.0-1.0)
  include_laterality: true            # Optional: Include left/right specificity
  include_specificity: true           # Optional: Include maximum code specificity
  coding_year: "2024"                 # Optional: ICD-10 version year
```

**Use Cases**:
- Primary and secondary diagnosis coding
- ICD-10-CM diagnosis classification
- ICD-10-PCS procedure coding
- Medical coding accuracy validation
- Clinical documentation improvement

**Input/Output**:
- **Input**: Clinical text, diagnosis descriptions, procedure notes
- **Output**: ICD-10 codes with confidence scores and supporting evidence

---

#### autonomize:cpt_code_model
**Purpose**: Specialized AI model for CPT and HCPCS procedure coding

**Component Mapping**:
```python
"autonomize:cpt_code_model": {
    "component": "AutonomizeModel",
    "config": {"selected_model": "CPT Code"},
    "dataType": "AutonomizeModel"
}
```

**Configuration Options**:
```yaml
config:
  selected_model: "CPT Code"          # Required: Model selection
  include_modifiers: true             # Optional: Include CPT modifiers
  include_hcpcs: true                 # Optional: Include HCPCS Level II codes
  bundling_rules: true                # Optional: Apply NCCI bundling rules
  confidence_threshold: 0.85          # Optional: Minimum confidence (0.0-1.0)
  cpt_year: "2024"                    # Optional: CPT version year
```

**Use Cases**:
- Procedure and service coding
- CPT modifier recommendation
- HCPCS Level II coding
- Revenue cycle optimization
- Billing accuracy improvement

**Input/Output**:
- **Input**: Procedure notes, operative reports, service descriptions
- **Output**: CPT/HCPCS codes with modifiers and confidence scores

---

#### autonomize:clinical_llm
**Purpose**: Advanced clinical language model for medical terminology and context understanding

**Component Mapping**:
```python
"autonomize:clinical_llm": {
    "component": "AutonomizeModel",
    "config": {"selected_model": "Clinical LLM"},
    "dataType": "AutonomizeModel"
}
```

**Configuration Options**:
```yaml
config:
  selected_model: "Clinical LLM"      # Required: Model selection
  terminology_extraction: true        # Optional: Extract medical terminology
  clinical_context: true              # Optional: Maintain clinical context
  medical_entity_recognition: true    # Optional: Recognize medical entities
  abbreviation_expansion: true        # Optional: Expand medical abbreviations
  specialty_context: "general"        # Optional: Medical specialty focus
```

**Use Cases**:
- Medical terminology extraction and normalization
- Clinical context understanding
- Medical entity recognition (drugs, procedures, anatomy)
- Clinical documentation analysis
- Medical abbreviation expansion

**Input/Output**:
- **Input**: Clinical text, medical documents, patient notes
- **Output**: Extracted entities, normalized terminology, clinical insights

---

### Healthcare Connectors

#### autonomize:ehr_connector
**Purpose**: HIPAA-compliant Electronic Health Record system integration

**Component Mapping**:
```python
"autonomize:ehr_connector": {
    "component": "EHRConnector",
    "config": {
        "ehr_system": "epic",
        "fhir_version": "R4",
        "authentication_type": "oauth2",
        "hipaa_compliant": True,
        "audit_logging": True
    },
    "dataType": "Data"
}
```

**Configuration Options**:
```yaml
config:
  ehr_system: "epic"                  # Required: EHR system type
  fhir_version: "R4"                  # Required: FHIR version
  authentication_type: "oauth2"       # Required: Auth method
  hipaa_compliant: true               # Required: HIPAA compliance
  audit_logging: true                 # Required: Audit trail
  clinical_context: true              # Optional: Include clinical context
  coding_history: true                # Optional: Access coding history
  timeout_seconds: 30                 # Optional: Request timeout
```

**Supported EHR Systems**:
- Epic (MyChart, Epic Hyperspace)
- Cerner (PowerChart)
- Allscripts
- athenahealth
- NextGen Healthcare

**Use Cases**:
- Patient data retrieval
- Clinical documentation access
- Medical history review
- Lab results integration
- Medication reconciliation

**Input/Output**:
- **Input**: Patient identifiers, search criteria, data requests
- **Output**: FHIR-compliant patient data, clinical documents

---

#### genesis:healthcare_validation_connector
**Purpose**: Healthcare-specific validation services with compliance checking

**Component Mapping**:
```python
"genesis:healthcare_validation_connector": {
    "component": "HealthcareValidationConnector",
    "config": {
        "validation_type": "comprehensive",
        "compliance_standards": ["CMS", "NCCI", "AMA"],
        "code_combination_checking": True,
        "audit_logging": True,
        "hipaa_compliant": True
    },
    "dataType": "Data"
}
```

**Configuration Options**:
```yaml
config:
  validation_type: "comprehensive"    # Required: Validation scope
  compliance_standards:               # Required: Standards to check
    - "CMS"                          # Centers for Medicare & Medicaid Services
    - "NCCI"                         # National Correct Coding Initiative
    - "AMA"                          # American Medical Association
  code_combination_checking: true     # Optional: Validate code combinations
  audit_logging: true                 # Required: Compliance audit trail
  hipaa_compliant: true               # Required: HIPAA compliance
  real_time_validation: true          # Optional: Real-time vs batch
```

**Validation Types**:
- **Basic**: Code format and structure validation
- **Standard**: Standard compliance checking (CMS, NCCI, AMA)
- **Comprehensive**: Full validation including code combinations
- **Custom**: User-defined validation rules

**Use Cases**:
- Medical code validation
- Compliance checking (CMS, NCCI, AMA guidelines)
- Code combination verification
- Billing accuracy validation
- Audit trail generation

**Input/Output**:
- **Input**: Medical codes, code combinations, clinical documentation
- **Output**: Validation results, compliance status, error details

---

## Component I/O Mappings

### Enhanced I/O Mappings for Healthcare Components

```python
healthcare_io_mappings = {
    # Autonomize Models
    "AutonomizeModel": {
        "input_field": "search_query",
        "output_field": "prediction",
        "output_types": ["Data"],
        "input_types": ["str", "Message", "Data"]
    },

    # Healthcare Connectors
    "EHRConnector": {
        "input_field": "patient_query",
        "output_field": "ehr_data",
        "output_types": ["Data"],
        "input_types": ["str", "Message", "Data"]
    },

    "HealthcareValidationConnector": {
        "input_field": "validation_request",
        "output_field": "validation_response",
        "output_types": ["Data"],
        "input_types": ["str", "Data"]
    }
}
```

## Migration Guidelines

### From MCP Tools to Healthcare Components

#### Before (MCP Tool Pattern):
```yaml
- id: medical-coding-tool
  type: genesis:mcp_tool
  config:
    tool_name: medical_coding_library
  provides:
  - useAs: tools
    in: agent
```

#### After (Enhanced Component Pattern):
```yaml
- id: medical-coding-model
  type: autonomize:icd10_code_model
  config:
    selected_model: "ICD-10 Code"
    confidence_threshold: 0.85
    include_laterality: true
  provides:
  - useAs: tools
    in: agent
```

### Migration Checklist

1. **Identify Component Purpose**:
   - AI/ML processing → Use autonomize models
   - Data access/integration → Use healthcare connectors
   - Simple APIs → Use genesis:api_request
   - Complex workflows → Keep as MCP tools

2. **Update Component Type**:
   - Change from `genesis:mcp_tool` to appropriate new type
   - Update configuration to match new component schema
   - Verify provides relationships remain valid

3. **Validate Configuration**:
   - Ensure all required configuration fields are present
   - Add HIPAA compliance settings where required
   - Configure appropriate timeouts and thresholds

4. **Test Integration**:
   - Validate with Genesis CLI
   - Test component connections and data flow
   - Verify HIPAA compliance requirements

## Security and Compliance

### HIPAA Compliance Requirements

All healthcare components must include:

```yaml
config:
  hipaa_compliant: true               # Required for healthcare data
  audit_logging: true                 # Required for access tracking
  encryption_in_transit: true         # Required for data transmission
  encryption_at_rest: true            # Required for data storage
```

### Best Practices

1. **Authentication**:
   - Use OAuth2 for EHR integrations
   - Store credentials in environment variables
   - Implement proper token refresh mechanisms

2. **Data Handling**:
   - Minimize PHI (Protected Health Information) exposure
   - Implement data anonymization where possible
   - Maintain audit trails for all PHI access

3. **Error Handling**:
   - Avoid exposing PHI in error messages
   - Implement graceful degradation for service failures
   - Log errors securely without PHI details

## Integration Examples

### Medical Coding Assistant Integration
```yaml
components:
  # ICD-10 Coding
  - id: icd-coding-model
    type: autonomize:icd10_code_model
    config:
      selected_model: "ICD-10 Code"
      confidence_threshold: 0.85
    provides:
    - useAs: tools
      in: coding-agent

  # CPT Coding
  - id: cpt-coding-model
    type: autonomize:cpt_code_model
    config:
      selected_model: "CPT Code"
      include_modifiers: true
    provides:
    - useAs: tools
      in: coding-agent

  # Clinical Language Understanding
  - id: clinical-nlp
    type: autonomize:clinical_llm
    config:
      selected_model: "Clinical LLM"
      terminology_extraction: true
    provides:
    - useAs: tools
      in: coding-agent

  # EHR Integration
  - id: ehr-integration
    type: autonomize:ehr_connector
    config:
      ehr_system: "epic"
      fhir_version: "R4"
      hipaa_compliant: true
    provides:
    - useAs: tools
      in: coding-agent

  # Validation
  - id: code-validation
    type: genesis:healthcare_validation_connector
    config:
      validation_type: "comprehensive"
      compliance_standards: ["CMS", "NCCI"]
    provides:
    - useAs: tools
      in: coding-agent
```

## Future Enhancements

### Planned Component Types

1. **autonomize:radiology_ai**: Medical imaging analysis
2. **autonomize:pathology_ai**: Pathology report analysis
3. **autonomize:drug_interaction**: Advanced drug interaction checking
4. **genesis:telemedicine_connector**: Telemedicine platform integration
5. **genesis:claims_connector**: Insurance claims processing
6. **genesis:pharmacy_connector**: Pharmacy and medication management

### Framework Extensions

1. **Component Discovery**: Automated identification of available healthcare components
2. **Configuration Validation**: Schema-based validation for component configurations
3. **Performance Monitoring**: Built-in metrics and monitoring for healthcare workflows
4. **Compliance Automation**: Automated compliance checking and reporting

## Conclusion

These healthcare component mappings provide a robust foundation for building HIPAA-compliant, efficient, and accurate healthcare AI workflows. By following the enhanced decision framework and using these specialized components, healthcare specifications will be more performant, secure, and compliant with industry standards.

For additional guidance, refer to the Enhanced Decision Framework documentation and the Medical Coding Assistant Agent as a reference implementation.