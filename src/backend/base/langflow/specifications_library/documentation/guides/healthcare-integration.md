# Healthcare Connector Integration Guide

Complete guide for integrating healthcare connectors into Genesis Agent specifications with HIPAA compliance and best practices.

## Overview

Healthcare connectors provide specialized integration capabilities for healthcare systems and workflows. This guide covers the setup, configuration, and implementation of all four healthcare connector types:

- **EHR Connector**: Electronic Health Record integration
- **Claims Connector**: Healthcare claims processing
- **Eligibility Connector**: Insurance eligibility verification
- **Pharmacy Connector**: Medication management and e-prescribing

## Prerequisites

### Required Environment Variables

Before using healthcare connectors, set up the following environment variables:

```bash
# EHR System Configuration
export EHR_BASE_URL="https://your-ehr-system.com/fhir"
export EHR_CLIENT_ID="your-ehr-client-id"
export EHR_CLIENT_SECRET="your-ehr-client-secret"

# Provider Information
export PROVIDER_NPI="1234567890"
export PRESCRIBER_NPI="0987654321"
export DEA_NUMBER="AB1234567"

# Claims and Eligibility
export PAYER_ID="your-payer-id"
export SUBMITTER_ID="your-submitter-id"

# Security and Compliance
export ENCRYPTION_KEY="your-encryption-key"
export AUDIT_ENDPOINT="https://your-audit-system.com/logs"
```

### HIPAA Compliance Setup

Ensure your environment meets HIPAA compliance requirements:

1. **Data Encryption**: All PHI data must be encrypted in transit and at rest
2. **Access Controls**: Implement role-based access to healthcare data
3. **Audit Logging**: Enable comprehensive logging for all PHI access
4. **Secure Storage**: Use secure storage solutions for healthcare credentials

## EHR Connector Integration

### Basic EHR Integration

```yaml
components:
  - id: patient-input
    type: genesis:chat_input
    name: Patient Information Input
    description: Accept patient ID or search criteria
    provides:
      - in: clinical-agent
        useAs: input
        description: Send patient query to clinical agent

  - id: ehr-connector
    type: genesis:ehr_connector
    name: Epic EHR Integration
    description: Retrieve patient data from Epic EHR system
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      base_url: "${EHR_BASE_URL}"
      operation: get_patient_data
    provides:
      - useAs: tools
        in: clinical-agent
        description: Provide EHR data access capability

  - id: clinical-agent
    type: genesis:agent
    name: Clinical Data Processor
    description: Process patient data with EHR integration
    config:
      system_prompt: |
        You are a clinical data processor with access to EHR systems.

        When processing patient data:
        1. Retrieve comprehensive patient information using the EHR connector
        2. Analyze clinical data following HIPAA guidelines
        3. Provide clinical insights while protecting PHI
        4. Generate structured clinical summaries

        HIPAA Compliance:
        - Never expose raw PHI in responses
        - Use clinical terminology and codes appropriately
        - Maintain patient privacy and confidentiality
        - Log all data access for audit compliance
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: clinical-output
        useAs: input
        description: Send processed clinical data

  - id: clinical-output
    type: genesis:chat_output
    name: Clinical Summary
    description: Display processed clinical information
    config:
      should_store_message: true
```

### Advanced EHR Operations

#### Multi-Operation EHR Agent

```yaml
- id: comprehensive-ehr
  type: genesis:ehr_connector
  name: Comprehensive EHR Access
  description: Multi-operation EHR connector for complete patient data
  asTools: true
  config:
    ehr_system: cerner
    fhir_version: R4
    authentication_type: oauth2
    base_url: "${EHR_BASE_URL}"
    operation: search_patients  # Can be changed by agent based on need
  provides:
    - useAs: tools
      in: comprehensive-agent
      description: Complete EHR access capability
```

#### Specialized EHR Prompting

```yaml
- id: ehr-specialist-prompt
  type: genesis:prompt
  name: EHR Specialist Instructions
  description: Specialized prompt for EHR data processing
  config:
    template: |
      You are an EHR integration specialist with access to comprehensive patient data.

      Available EHR Operations:
      - search_patients: Find patients based on criteria
      - get_patient_data: Retrieve comprehensive patient information
      - get_observations: Get vital signs, lab results, and clinical observations
      - get_medications: Retrieve current and historical medications
      - get_conditions: Get patient diagnoses and conditions
      - get_providers: Access provider information and care team
      - get_care_team: Retrieve multidisciplinary care team information

      Clinical Data Processing Guidelines:
      1. Start with patient search or direct data retrieval
      2. Gather relevant clinical context (conditions, medications, observations)
      3. Analyze data for clinical patterns and insights
      4. Provide evidence-based clinical recommendations
      5. Ensure all data handling complies with HIPAA requirements

      FHIR R4 Standards:
      - Use proper FHIR resource structures
      - Reference appropriate terminology systems (LOINC, SNOMED CT, ICD-10)
      - Maintain data integrity across all operations
      - Follow clinical coding best practices

      Output structured clinical summaries with:
      - Patient demographics (age, gender, relevant identifiers)
      - Clinical conditions and their status
      - Current medications and therapy plans
      - Recent observations and vital signs
      - Care team and provider information
      - Clinical recommendations and next steps
  provides:
    - useAs: system_prompt
      in: ehr-specialist-agent
      description: Comprehensive EHR processing instructions
```

## Claims Connector Integration

### Basic Claims Processing

```yaml
components:
  - id: claims-input
    type: genesis:chat_input
    name: Claims Data Input
    description: Accept claims information for processing
    provides:
      - in: claims-agent
        useAs: input
        description: Send claims data to processing agent

  - id: claims-connector
    type: genesis:claims_connector
    name: Claims Processing System
    description: Submit and track healthcare claims
    asTools: true
    config:
      clearinghouse: change_healthcare
      provider_npi: "${PROVIDER_NPI}"
      test_mode: true  # Use false for production
      operation: submit_claim
    provides:
      - useAs: tools
        in: claims-agent
        description: Claims processing capability

  - id: claims-agent
    type: genesis:agent
    name: Claims Processing Agent
    description: Handle healthcare claims submission and tracking
    config:
      system_prompt: |
        You are a healthcare claims processing specialist.

        Claims Processing Workflow:
        1. Validate claim data for completeness and accuracy
        2. Check for proper coding (CPT, ICD-10, HCPCS)
        3. Submit claims through appropriate clearinghouse
        4. Track claim status and handle rejections
        5. Process remittance advice and payment posting

        Claim Validation Checklist:
        - Patient demographics and insurance information
        - Provider NPI and facility information
        - Service dates and procedure codes
        - Diagnosis codes and medical necessity
        - Prior authorization requirements

        Always ensure claims compliance with:
        - CMS guidelines and regulations
        - Payer-specific requirements
        - HIPAA privacy and security rules
        - State and federal healthcare regulations
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: claims-output
        useAs: input
        description: Send claims processing results

  - id: claims-output
    type: genesis:chat_output
    name: Claims Processing Results
    description: Display claims submission and tracking information
```

### Prior Authorization Integration

```yaml
- id: prior-auth-connector
  type: genesis:claims_connector
  name: Prior Authorization System
  description: Handle prior authorization requests and tracking
  asTools: true
  config:
    clearinghouse: availity
    payer_id: "${PAYER_ID}"
    test_mode: false
    operation: prior_authorization
  provides:
    - useAs: tools
      in: auth-agent
      description: Prior authorization processing tools
```

## Eligibility Connector Integration

### Real-Time Eligibility Verification

```yaml
components:
  - id: eligibility-input
    type: genesis:chat_input
    name: Patient Insurance Information
    description: Accept patient insurance details for verification
    provides:
      - in: eligibility-agent
        useAs: input
        description: Send patient data for eligibility check

  - id: eligibility-connector
    type: genesis:eligibility_connector
    name: Real-Time Eligibility Verification
    description: Verify patient insurance eligibility and benefits
    asTools: true
    config:
      eligibility_service: availity
      provider_npi: "${PROVIDER_NPI}"
      real_time_mode: true
      cache_duration_minutes: 15
      operation: verify_eligibility
    provides:
      - useAs: tools
        in: eligibility-agent
        description: Real-time eligibility verification tools

  - id: eligibility-agent
    type: genesis:agent
    name: Eligibility Verification Agent
    description: Process insurance eligibility and benefit verification
    config:
      system_prompt: |
        You are an insurance eligibility verification specialist.

        Eligibility Verification Process:
        1. Verify patient active insurance coverage
        2. Check benefit plan details and limitations
        3. Determine copays, deductibles, and coinsurance
        4. Validate network provider status
        5. Calculate patient financial responsibility

        Key Information to Verify:
        - Active coverage effective dates
        - Benefit plan type and tier
        - Deductible amounts and accumulations
        - Out-of-pocket maximum status
        - Prior authorization requirements
        - Network provider validation

        Provide clear eligibility summaries including:
        - Coverage status (active/inactive/pending)
        - Benefit details and limitations
        - Patient cost-sharing information
        - Prior authorization requirements
        - Network status and referral needs

        Always maintain HIPAA compliance and protect patient information.
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: eligibility-output
        useAs: input
        description: Send eligibility verification results

  - id: eligibility-output
    type: genesis:chat_output
    name: Eligibility Verification Results
    description: Display insurance eligibility and benefit information
```

### Benefit Analysis Integration

```yaml
- id: benefit-analyzer
  type: genesis:eligibility_connector
  name: Comprehensive Benefit Analysis
  description: Detailed benefit analysis and cost calculation
  asTools: true
  config:
    eligibility_service: change_healthcare
    payer_list: ["aetna", "anthem", "cigna", "humana", "united_health"]
    real_time_mode: false
    cache_duration_minutes: 30
    operation: get_benefit_summary
  provides:
    - useAs: tools
      in: benefit-analysis-agent
      description: Comprehensive benefit analysis tools
```

## Pharmacy Connector Integration

### E-Prescribing Integration

```yaml
components:
  - id: prescription-input
    type: genesis:chat_input
    name: Prescription Information
    description: Accept prescription details for processing
    provides:
      - in: pharmacy-agent
        useAs: input
        description: Send prescription data to pharmacy agent

  - id: pharmacy-connector
    type: genesis:pharmacy_connector
    name: E-Prescribing System
    description: Electronic prescription management with safety checks
    asTools: true
    config:
      pharmacy_network: surescripts
      prescriber_npi: "${PRESCRIBER_NPI}"
      dea_number: "${DEA_NUMBER}"
      interaction_checking: true
      formulary_checking: true
      operation: send_prescription
    provides:
      - useAs: tools
        in: pharmacy-agent
        description: E-prescribing and medication management tools

  - id: pharmacy-agent
    type: genesis:agent
    name: Medication Management Agent
    description: Handle e-prescribing and medication management
    config:
      system_prompt: |
        You are a medication management specialist with e-prescribing capabilities.

        Medication Management Workflow:
        1. Review patient medication history and allergies
        2. Check for drug interactions and contraindications
        3. Verify formulary coverage and alternatives
        4. Generate and transmit electronic prescriptions
        5. Monitor medication therapy and adherence

        Safety Checks Required:
        - Drug-drug interactions
        - Drug-allergy interactions
        - Dosage verification and appropriateness
        - Formulary status and coverage
        - Prior authorization requirements
        - Pregnancy and age-related considerations

        E-Prescribing Standards:
        - Follow NCPDP SCRIPT standards
        - Use proper NDC codes and quantities
        - Include appropriate diagnosis codes
        - Verify pharmacy network participation
        - Ensure DEA compliance for controlled substances

        Always prioritize patient safety and medication appropriateness.
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: pharmacy-output
        useAs: input
        description: Send prescription processing results

  - id: pharmacy-output
    type: genesis:chat_output
    name: Prescription Processing Results
    description: Display prescription status and medication information
```

### Medication Therapy Management

```yaml
- id: mtm-connector
  type: genesis:pharmacy_connector
  name: Medication Therapy Management
  description: Comprehensive medication management and optimization
  asTools: true
  config:
    pharmacy_network: ncpdp
    drug_database: first_databank
    interaction_checking: true
    formulary_checking: true
    operation: medication_history
  provides:
    - useAs: tools
      in: pharmacist-agent
      description: MTM and medication review tools
```

## Multi-Connector Healthcare Integration

### Comprehensive Healthcare Workflow

```yaml
name: Comprehensive Healthcare Integration
description: End-to-end healthcare workflow with multiple system integrations
version: "1.0.0"
agentGoal: Orchestrate complete healthcare workflow from patient data to billing

# Healthcare enterprise metadata
domain: autonomize.ai
subDomain: healthcare-integration
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation
toolsUse: true

# HIPAA compliance
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

components:
  - id: patient-input
    type: genesis:chat_input
    name: Patient Workflow Input
    description: Accept patient information for comprehensive processing

  - id: healthcare-prompt
    type: genesis:prompt
    name: Healthcare Integration Instructions
    description: Comprehensive healthcare workflow orchestration
    config:
      template: |
        You are a healthcare workflow orchestrator with access to multiple systems:

        1. EHR System: Complete patient clinical data
        2. Eligibility System: Insurance verification and benefits
        3. Claims System: Billing and prior authorization
        4. Pharmacy System: Medication management and e-prescribing

        Comprehensive Workflow Process:
        1. Patient Data Collection: Retrieve complete patient information from EHR
        2. Insurance Verification: Verify coverage and determine benefits
        3. Clinical Assessment: Analyze patient data for treatment planning
        4. Medication Review: Check current medications and interactions
        5. Treatment Planning: Develop evidence-based treatment recommendations
        6. Prior Authorization: Handle required authorizations
        7. Prescription Management: Process medication orders safely
        8. Billing Coordination: Submit appropriate claims

        Quality and Safety Standards:
        - Follow evidence-based clinical guidelines
        - Ensure medication safety and appropriateness
        - Verify insurance coverage before treatment
        - Maintain HIPAA compliance throughout workflow
        - Document all decisions with clinical rationale

        Always prioritize patient safety, clinical quality, and regulatory compliance.

  - id: ehr-system
    type: genesis:ehr_connector
    name: EHR Integration
    description: Comprehensive patient data access
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      base_url: "${EHR_BASE_URL}"
      operation: get_patient_data

  - id: eligibility-system
    type: genesis:eligibility_connector
    name: Insurance Eligibility
    description: Real-time eligibility verification
    asTools: true
    config:
      eligibility_service: availity
      provider_npi: "${PROVIDER_NPI}"
      real_time_mode: true
      operation: verify_eligibility

  - id: claims-system
    type: genesis:claims_connector
    name: Claims Processing
    description: Claims submission and prior authorization
    asTools: true
    config:
      clearinghouse: change_healthcare
      provider_npi: "${PROVIDER_NPI}"
      test_mode: false
      operation: submit_claim

  - id: pharmacy-system
    type: genesis:pharmacy_connector
    name: Pharmacy Integration
    description: E-prescribing and medication management
    asTools: true
    config:
      pharmacy_network: surescripts
      prescriber_npi: "${PRESCRIBER_NPI}"
      interaction_checking: true
      formulary_checking: true
      operation: send_prescription

  - id: healthcare-orchestrator
    type: genesis:agent
    name: Healthcare Workflow Orchestrator
    description: Orchestrates comprehensive healthcare workflow
    config:
      agent_llm: Azure OpenAI
      model_name: gpt-4
      temperature: 0.1
      max_tokens: 4000
      handle_parsing_errors: true
      max_iterations: 15

  - id: healthcare-output
    type: genesis:chat_output
    name: Healthcare Workflow Results
    description: Comprehensive healthcare workflow results
    config:
      should_store_message: true

# Configuration variables
variables:
  - name: ehr_base_url
    type: string
    required: true
    description: EHR system base URL

  - name: provider_npi
    type: string
    required: true
    description: National Provider Identifier

# Healthcare KPIs
kpis:
  - name: Workflow Completion Rate
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Percentage of workflows completed successfully

  - name: HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: HIPAA compliance rating

  - name: Clinical Accuracy
    category: Quality
    valueType: percentage
    target: 98
    unit: '%'
    description: Accuracy of clinical recommendations
```

## Configuration Best Practices

### Environment Variable Management

```bash
# Development Environment (.env.dev)
EHR_BASE_URL="https://sandbox-ehr.example.com/fhir"
CLAIMS_TEST_MODE="true"
ELIGIBILITY_CACHE_DURATION="5"  # Shorter cache for testing

# Production Environment (.env.prod)
EHR_BASE_URL="https://prod-ehr.example.com/fhir"
CLAIMS_TEST_MODE="false"
ELIGIBILITY_CACHE_DURATION="15"  # Standard cache duration
```

### Security Configuration

```yaml
# Always include security metadata for healthcare agents
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

# Required healthcare variables
variables:
  - name: encryption_key
    type: string
    required: true
    description: Encryption key for PHI data

  - name: audit_endpoint
    type: string
    required: true
    description: Audit logging endpoint

# HIPAA compliance KPIs
kpis:
  - name: HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: HIPAA compliance rating
```

### Error Handling and Fallbacks

```yaml
config:
  # Enable robust error handling
  handle_parsing_errors: true
  max_iterations: 10

  # Healthcare-specific timeouts
  timeout_seconds: 30
  retry_count: 3

  # Fallback to mock mode if services unavailable
  mock_fallback: true
```

## Testing and Validation

### Development Testing

1. **Mock Mode Testing**: Use `test_mode: true` for all connectors
2. **Sandbox Environments**: Connect to healthcare sandbox systems
3. **Data Validation**: Verify FHIR resource compliance
4. **Security Testing**: Validate PHI protection and audit logging

### Production Validation

1. **Connectivity Testing**: Verify all healthcare system connections
2. **Compliance Auditing**: Ensure HIPAA compliance measures are active
3. **Performance Monitoring**: Track response times and error rates
4. **Clinical Accuracy**: Validate clinical recommendations and data processing

## Troubleshooting Guide

### Common Issues

#### Authentication Errors
```
Error: "OAuth2 authentication failed"
Solution:
- Verify CLIENT_ID and CLIENT_SECRET environment variables
- Check token expiration and refresh mechanisms
- Ensure proper scopes are configured
```

#### FHIR Version Compatibility
```
Error: "Unsupported FHIR version"
Solution:
- Verify EHR system FHIR version support
- Update fhir_version configuration to match
- Check resource structure compatibility
```

#### Network Connectivity
```
Error: "Connection timeout to healthcare service"
Solution:
- Verify network connectivity and firewall rules
- Check service endpoint URLs and availability
- Increase timeout values if necessary
```

#### HIPAA Compliance Warnings
```
Warning: "PHI data detected in logs"
Solution:
- Enable PHI sanitization in logging configuration
- Verify audit logging is properly configured
- Review error handling to prevent PHI exposure
```

### Performance Optimization

1. **Caching Strategy**: Use appropriate cache durations for eligibility data
2. **Batch Operations**: Combine multiple operations when possible
3. **Connection Pooling**: Optimize connection management for high volume
4. **Rate Limiting**: Respect healthcare API rate limits

## Support and Resources

### Healthcare Standards References
- **FHIR R4**: https://hl7.org/fhir/R4/
- **HL7 Standards**: https://www.hl7.org/implement/standards/
- **EDI Standards**: https://www.x12.org/standards/
- **NCPDP SCRIPT**: https://www.ncpdp.org/NCPDP/media/pdf/SCRIPT-Standard-Implementation-Guide.pdf

### Compliance Resources
- **HIPAA Guidelines**: https://www.hhs.gov/hipaa/
- **CMS Regulations**: https://www.cms.gov/
- **ONC Certification**: https://www.healthit.gov/

### Technical Support
- **Component Documentation**: See [Component Catalog](../components/component-catalog.md)
- **Pattern Examples**: See [Pattern Catalog](../patterns/pattern-catalog.md)
- **Schema Reference**: See [Specification Schema](../schema/specification-schema.md)
- **HIPAA Compliance**: See [HIPAA Best Practices Guide](hipaa-compliance.md)

## Next Steps

1. **Choose Integration Pattern**: Select appropriate healthcare pattern for your use case
2. **Configure Environment**: Set up required environment variables and credentials
3. **Implement Specification**: Create healthcare agent specification following this guide
4. **Test Integration**: Validate functionality in development environment
5. **Deploy Securely**: Ensure HIPAA compliance before production deployment

For additional guidance, see the [HIPAA Compliance Best Practices Guide](hipaa-compliance.md) and [Clinical Workflow Creation Guide](clinical-workflow.md).