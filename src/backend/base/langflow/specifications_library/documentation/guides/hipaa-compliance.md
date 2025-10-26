# HIPAA Compliance Best Practices Guide

Comprehensive guide for implementing HIPAA-compliant healthcare AI workflows using Genesis Agent specifications.

## Overview

The Health Insurance Portability and Accountability Act (HIPAA) requires strict protection of Protected Health Information (PHI). This guide provides best practices for creating HIPAA-compliant healthcare agents and workflows using Genesis specifications.

## HIPAA Fundamentals

### Protected Health Information (PHI)

PHI includes any individually identifiable health information, including:

- **Demographic Information**: Names, addresses, birth dates, SSNs
- **Medical Information**: Diagnoses, treatments, medications, test results
- **Financial Information**: Insurance details, billing information, payment data
- **Digital Identifiers**: IP addresses, device identifiers, biometric data

### HIPAA Requirements for AI Systems

1. **Privacy Rule**: Limit use and disclosure of PHI
2. **Security Rule**: Implement physical, administrative, and technical safeguards
3. **Breach Notification Rule**: Report PHI breaches within 60 days
4. **Enforcement Rule**: Compliance monitoring and penalties

## Genesis Agent HIPAA Compliance

### Required Metadata for PHI Handling

All healthcare agents handling PHI must include specific metadata:

```yaml
# Required HIPAA compliance metadata
securityInfo:
  visibility: Private              # Required for PHI data
  confidentiality: High           # High security classification
  gdprSensitive: true            # GDPR compliance flag

# Healthcare domain classification
domain: autonomize.ai
subDomain: healthcare-{specific_area}
targetUser: internal             # Restrict to internal users
valueGeneration: ProcessAutomation

# Required compliance variables
variables:
  - name: encryption_key
    type: string
    required: true
    description: Encryption key for PHI data protection

  - name: audit_endpoint
    type: string
    required: true
    description: Audit logging endpoint for compliance tracking

  - name: access_log_retention_days
    type: integer
    required: true
    default: 2555  # 7 years as required by HIPAA
    description: Access log retention period in days
```

### HIPAA Compliance KPIs

Include mandatory compliance metrics:

```yaml
kpis:
  - name: HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Overall HIPAA compliance rating

  - name: PHI Access Audit Rate
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Percentage of PHI access events logged

  - name: Data Encryption Rate
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Percentage of PHI data encrypted at rest and in transit

  - name: Breach Detection Time
    category: Security
    valueType: numeric
    target: 5
    unit: 'minutes'
    description: Average time to detect potential PHI breaches

  - name: Access Control Violations
    category: Security
    valueType: numeric
    target: 0
    unit: 'incidents'
    description: Number of unauthorized PHI access attempts
```

## Administrative Safeguards

### Access Control Implementation

```yaml
# Role-based access control variables
variables:
  - name: authorized_roles
    type: array
    required: true
    description: List of roles authorized to access PHI
    default: ["clinical_staff", "billing_admin", "compliance_officer"]

  - name: minimum_clearance_level
    type: string
    required: true
    description: Minimum security clearance for PHI access
    default: "confidential"

  - name: access_approval_required
    type: boolean
    required: true
    description: Whether PHI access requires approval
    default: true
```

### Agent System Prompts for Compliance

```yaml
- id: hipaa-compliant-prompt
  type: genesis:prompt
  name: HIPAA Compliant Processing Instructions
  description: Standard HIPAA compliance prompt for healthcare agents
  config:
    template: |
      You are a HIPAA-compliant healthcare AI assistant with strict PHI protection requirements.

      HIPAA COMPLIANCE REQUIREMENTS:

      1. PHI Protection:
         - Never display, log, or transmit raw PHI data
         - Use de-identified data whenever possible
         - Mask patient identifiers in all outputs
         - Replace names with generic identifiers (e.g., "Patient A")

      2. Minimum Necessary Standard:
         - Only access PHI necessary for the specific task
         - Limit data processing to essential elements
         - Request additional data only when required

      3. Access Logging:
         - Log all PHI access attempts
         - Record user, timestamp, and purpose
         - Document data elements accessed
         - Note any unusual access patterns

      4. Data Security:
         - Ensure all PHI is encrypted in transit and at rest
         - Use secure communication channels only
         - Verify user authorization before PHI access
         - Implement session timeouts for security

      5. Breach Response:
         - Immediately report suspected PHI breaches
         - Document any unauthorized access attempts
         - Preserve audit trails for investigation
         - Follow incident response procedures

      PROCESSING GUIDELINES:

      For Patient Data:
      - Use clinical terminology and medical codes
      - Focus on medical necessity and clinical relevance
      - Provide evidence-based recommendations
      - Maintain professional medical standards

      For Outputs:
      - Generate de-identified clinical summaries
      - Use aggregate data when possible
      - Provide statistical analysis without identifiers
      - Include compliance verification statements

      PROHIBITED ACTIONS:
      - Never include patient names, addresses, or SSNs in outputs
      - Do not store PHI in temporary files or caches
      - Avoid creating logs that contain raw PHI data
      - Never transmit PHI over unsecured channels

      Always prioritize patient privacy and HIPAA compliance over functionality.
  provides:
    - useAs: system_prompt
      in: healthcare-agent
      description: HIPAA compliance instructions
```

## Physical Safeguards

### Secure Environment Configuration

```yaml
# Physical security requirements
variables:
  - name: secure_facility_required
    type: boolean
    required: true
    description: Whether processing requires secure facility
    default: true

  - name: workstation_security_level
    type: string
    required: true
    description: Required workstation security level
    default: "high_security"

  - name: media_disposal_protocol
    type: string
    required: true
    description: Protocol for secure disposal of PHI-containing media
    default: "dod_5220_22_m"
```

## Technical Safeguards

### Data Encryption

All healthcare connectors implement automatic encryption:

```yaml
- id: secure-ehr-connector
  type: genesis:ehr_connector
  name: Secure EHR Integration
  description: HIPAA-compliant EHR connector with encryption
  asTools: true
  config:
    ehr_system: epic
    fhir_version: R4
    authentication_type: oauth2
    base_url: "${EHR_BASE_URL}"

    # HIPAA security configurations
    encryption_enabled: true
    encryption_algorithm: "AES-256-GCM"
    tls_version: "1.3"
    certificate_validation: true

    # Audit logging
    audit_logging: true
    audit_endpoint: "${AUDIT_ENDPOINT}"
    log_level: "detailed"

    # Access controls
    session_timeout_minutes: 30
    max_failed_attempts: 3
    account_lockout_duration_minutes: 60
  provides:
    - useAs: tools
      in: secure-healthcare-agent
      description: Secure PHI access capability
```

### Audit Logging Configuration

```yaml
# Comprehensive audit logging setup
variables:
  - name: audit_log_format
    type: string
    required: true
    description: Format for audit log entries
    default: "json_structured"

  - name: log_retention_policy
    type: object
    required: true
    description: Log retention and archival policy
    default:
      retention_days: 2555  # 7 years
      archival_location: "secure_storage"
      deletion_method: "secure_wipe"

  - name: real_time_monitoring
    type: boolean
    required: true
    description: Enable real-time audit monitoring
    default: true
```

### Access Control Validation

```yaml
- id: access-validator
  type: genesis:mcp_tool
  name: HIPAA Access Validator
  description: Validate user authorization for PHI access
  asTools: true
  config:
    tool_name: hipaa_access_validator
    description: |
      Validate user access to PHI data according to HIPAA requirements.

      This tool:
      1. Verifies user identity and authentication
      2. Checks role-based access permissions
      3. Validates need-to-know requirements
      4. Logs all access attempts
      5. Enforces session timeouts

      Required parameters:
      - user_id: Authenticated user identifier
      - requested_data_type: Type of PHI requested
      - access_purpose: Clinical or administrative purpose
      - patient_id: Patient identifier (optional)

      Returns access decision with audit trail entry.

    # Security configurations
    require_mfa: true
    session_timeout_minutes: 30
    audit_all_attempts: true
  provides:
    - useAs: tools
      in: healthcare-agent
      description: PHI access validation capability
```

## Data De-identification

### Automatic De-identification

```yaml
- id: deidentification-processor
  type: genesis:agent
  name: PHI De-identification Processor
  description: Automatically de-identify PHI data for compliance
  config:
    system_prompt: |
      You are a PHI de-identification specialist responsible for removing or masking identifiable information.

      De-identification Requirements (HIPAA Safe Harbor Method):

      Direct Identifiers to Remove:
      1. Names (last, first, middle, maiden)
      2. Geographic subdivisions smaller than state
      3. Dates related to individual (except year for age >89)
      4. Phone and fax numbers
      5. Email addresses
      6. Social Security numbers
      7. Medical record numbers
      8. Health plan beneficiary numbers
      9. Account numbers
      10. Certificate/license numbers
      11. Vehicle identifiers and license plates
      12. Device identifiers and serial numbers
      13. Web URLs
      14. IP addresses
      15. Biometric identifiers
      16. Full face photographs
      17. Other unique identifying numbers or codes

      De-identification Process:
      1. Replace direct identifiers with generic labels
      2. Use date shifting for temporal information
      3. Replace specific locations with general regions
      4. Mask numeric identifiers with random values
      5. Generate synthetic identifiers when needed

      Example Transformations:
      - "John Doe" → "Patient A"
      - "123 Main St, New York, NY 10001" → "Major Metropolitan Area, Northeast"
      - "DOB: 03/15/1975" → "Age: 48 years"
      - "MRN: 123456789" → "Patient ID: XXXX1234"
      - "SSN: 123-45-6789" → "[SSN REMOVED]"

      Quality Standards:
      - Maintain clinical utility of de-identified data
      - Preserve temporal relationships where possible
      - Ensure consistency across related records
      - Document all de-identification methods used

      Always verify that de-identified data cannot be re-identified through combination with other data sources.
    temperature: 0.1
    max_tokens: 2000
    handle_parsing_errors: true
  provides:
    - in: deidentified-output
      useAs: input
      description: Send de-identified data
```

## Business Associate Agreements

### Third-Party Integration Requirements

```yaml
# Business Associate Agreement compliance
variables:
  - name: baa_required_vendors
    type: array
    required: true
    description: List of vendors requiring BAA agreements
    default: ["cloud_providers", "analytics_platforms", "audit_services"]

  - name: vendor_compliance_verification
    type: boolean
    required: true
    description: Verify vendor HIPAA compliance before integration
    default: true

  - name: data_processing_agreements
    type: array
    required: true
    description: Required data processing agreements
    default: ["baa", "privacy_agreement", "security_agreement"]
```

### Cloud Service Configuration

```yaml
# HIPAA-compliant cloud configuration
variables:
  - name: cloud_encryption_requirements
    type: object
    required: true
    description: Cloud encryption requirements
    default:
      at_rest: "AES-256"
      in_transit: "TLS-1.3"
      key_management: "customer_managed"

  - name: data_residency_requirements
    type: object
    required: true
    description: Data location and residency requirements
    default:
      allowed_regions: ["us-east-1", "us-west-2"]
      prohibited_regions: ["international"]
      data_sovereignty: "us_only"
```

## Incident Response

### Breach Detection and Response

```yaml
- id: breach-detector
  type: genesis:agent
  name: HIPAA Breach Detection Agent
  description: Monitor and detect potential PHI breaches
  config:
    system_prompt: |
      You are a HIPAA breach detection specialist monitoring for potential PHI security incidents.

      Breach Detection Criteria:
      1. Unauthorized PHI access or disclosure
      2. PHI data transmitted over unsecured channels
      3. Lost or stolen devices containing PHI
      4. Ransomware or malware affecting PHI systems
      5. Inadvertent PHI disclosure to unauthorized parties
      6. System intrusions affecting PHI databases

      Incident Assessment Process:
      1. Identify the scope and nature of the incident
      2. Determine if PHI was involved
      3. Assess the risk of harm to individuals
      4. Document all findings and evidence
      5. Classify the incident severity level

      Required Actions for Suspected Breaches:
      1. Immediate containment of the incident
      2. Assessment of PHI involved
      3. Notification to compliance officer within 1 hour
      4. Documentation of incident details
      5. Preservation of evidence for investigation

      Breach Classification:
      - Level 1: Minor incident, no PHI exposure
      - Level 2: Limited PHI exposure, low risk
      - Level 3: Significant PHI exposure, moderate risk
      - Level 4: Major breach, high risk to individuals
      - Level 5: Massive breach, immediate reporting required

      For Level 3+ incidents:
      - Notify legal and compliance teams immediately
      - Begin breach notification process
      - Prepare regulatory reporting documentation
      - Implement additional safeguards

      Always err on the side of caution when assessing potential breaches.
    temperature: 0.1
    max_tokens: 3000
    handle_parsing_errors: true
  provides:
    - in: incident-response-output
      useAs: input
      description: Send breach assessment results
```

### Incident Documentation

```yaml
# Incident response variables
variables:
  - name: incident_response_team
    type: array
    required: true
    description: List of incident response team contacts
    default: ["compliance_officer", "legal_counsel", "it_security", "privacy_officer"]

  - name: breach_notification_timeline
    type: object
    required: true
    description: Required notification timelines
    default:
      internal_notification_hours: 1
      compliance_assessment_hours: 24
      regulatory_notification_days: 60
      individual_notification_days: 60

  - name: incident_documentation_requirements
    type: array
    required: true
    description: Required incident documentation
    default: ["incident_timeline", "phi_assessment", "risk_analysis", "mitigation_actions"]
```

## Compliance Monitoring

### Automated Compliance Checking

```yaml
- id: compliance-monitor
  type: genesis:agent
  name: HIPAA Compliance Monitor
  description: Continuous monitoring of HIPAA compliance status
  config:
    system_prompt: |
      You are a HIPAA compliance monitoring specialist responsible for ongoing compliance assessment.

      Compliance Monitoring Areas:
      1. Access Controls: Verify proper user authentication and authorization
      2. Audit Logs: Ensure comprehensive logging of PHI access
      3. Data Encryption: Confirm encryption standards are maintained
      4. Training Compliance: Verify staff HIPAA training currency
      5. Risk Assessments: Monitor completion of required assessments
      6. Incident Response: Track incident response effectiveness

      Daily Monitoring Checklist:
      □ Review access logs for unusual patterns
      □ Verify encryption status of PHI data
      □ Check system security updates and patches
      □ Monitor failed authentication attempts
      □ Review incident reports and resolutions
      □ Validate backup and recovery processes

      Weekly Monitoring Tasks:
      □ Conduct vulnerability scans
      □ Review user access permissions
      □ Validate data retention policies
      □ Check vendor compliance status
      □ Assess training completion rates
      □ Review policy updates and changes

      Monthly Compliance Reports:
      □ Generate compliance scorecard
      □ Document any compliance gaps
      □ Recommend corrective actions
      □ Update risk assessments
      □ Report to compliance committee

      Red Flags Requiring Immediate Attention:
      - Unauthorized PHI access attempts
      - Failed encryption of PHI data
      - Missing audit log entries
      - Expired user access credentials
      - Unpatched security vulnerabilities
      - Vendor compliance violations

      Generate detailed compliance reports with specific recommendations for any issues identified.
    temperature: 0.1
    max_tokens: 2000
    handle_parsing_errors: true
  provides:
    - in: compliance-report-output
      useAs: input
      description: Send compliance monitoring results
```

### Compliance Dashboard KPIs

```yaml
kpis:
  # Core HIPAA Compliance Metrics
  - name: Overall HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Aggregate HIPAA compliance rating

  - name: PHI Access Control Compliance
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Proper access controls for PHI data

  - name: Audit Log Completeness
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Complete audit logging coverage

  - name: Data Encryption Compliance
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: PHI data encryption compliance rate

  # Training and Awareness
  - name: Staff HIPAA Training Current
    category: Training
    valueType: percentage
    target: 100
    unit: '%'
    description: Percentage of staff with current HIPAA training

  - name: Security Awareness Score
    category: Training
    valueType: percentage
    target: 95
    unit: '%'
    description: Staff security awareness assessment scores

  # Risk Management
  - name: Risk Assessment Currency
    category: Risk
    valueType: percentage
    target: 100
    unit: '%'
    description: Current risk assessments for all PHI systems

  - name: Vulnerability Remediation Rate
    category: Risk
    valueType: percentage
    target: 95
    unit: '%'
    description: Rate of security vulnerability remediation

  # Incident Response
  - name: Incident Response Time
    category: Incident
    valueType: numeric
    target: 1
    unit: 'hours'
    description: Average time to respond to security incidents

  - name: Breach Notification Compliance
    category: Incident
    valueType: percentage
    target: 100
    unit: '%'
    description: Compliance with breach notification timelines
```

## Sample HIPAA-Compliant Specification

### Complete Example

```yaml
name: HIPAA Compliant Patient Data Processor
description: Secure processing of patient health information with full HIPAA compliance
version: "1.0.0"
agentGoal: Process patient health information securely while maintaining HIPAA compliance

# HIPAA compliance metadata
id: urn:agent:genesis:autonomize.ai:hipaa_patient_processor:1.0.0
fullyQualifiedName: genesis.autonomize.ai.hipaa_patient_processor
domain: autonomize.ai
subDomain: healthcare-clinical-processing
environment: production
agentOwner: compliance@autonomize.ai
agentOwnerDisplayName: HIPAA Compliance Team
email: compliance@autonomize.ai
status: ACTIVE

# Classification
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
agencyLevel: KnowledgeDrivenWorkflow
toolsUse: true
learningCapability: None

# Security and compliance
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

# HIPAA compliance variables
variables:
  - name: encryption_key
    type: string
    required: true
    description: AES-256 encryption key for PHI protection

  - name: audit_endpoint
    type: string
    required: true
    description: Secure audit logging endpoint

  - name: authorized_roles
    type: array
    required: true
    description: Roles authorized for PHI access
    default: ["physician", "nurse", "medical_assistant", "billing_specialist"]

  - name: session_timeout_minutes
    type: integer
    required: true
    description: Session timeout for security
    default: 30

# HIPAA compliance KPIs
kpis:
  - name: HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Overall HIPAA compliance rating

  - name: PHI Access Audit Rate
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Percentage of PHI access events logged

  - name: Data Encryption Rate
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: Percentage of PHI data encrypted

  - name: Clinical Accuracy
    category: Quality
    valueType: percentage
    target: 98
    unit: '%'
    description: Accuracy of clinical data processing

  - name: Response Time
    category: Performance
    valueType: numeric
    target: 5
    unit: 'seconds'
    description: Average response time for PHI processing

components:
  - id: patient-input
    type: genesis:chat_input
    name: Secure Patient Data Input
    description: HIPAA-compliant patient data entry point
    provides:
      - in: access-validator
        useAs: input
        description: Send request to access validator

  - id: access-validator
    type: genesis:mcp_tool
    name: HIPAA Access Validator
    description: Validate user authorization for PHI access
    asTools: true
    config:
      tool_name: hipaa_access_validator
      description: Validate user access to PHI data according to HIPAA requirements
      require_mfa: true
      session_timeout_minutes: 30
      audit_all_attempts: true
    provides:
      - useAs: tools
        in: hipaa-agent
        description: PHI access validation

  - id: ehr-connector
    type: genesis:ehr_connector
    name: Secure EHR Integration
    description: HIPAA-compliant EHR data access
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      base_url: "${EHR_BASE_URL}"
      encryption_enabled: true
      audit_logging: true
      session_timeout_minutes: 30
    provides:
      - useAs: tools
        in: hipaa-agent
        description: Secure EHR data access

  - id: hipaa-prompt
    type: genesis:prompt
    name: HIPAA Compliance Instructions
    description: Comprehensive HIPAA compliance prompt
    config:
      template: |
        You are a HIPAA-compliant healthcare AI assistant with strict PHI protection requirements.

        MANDATORY HIPAA COMPLIANCE REQUIREMENTS:

        1. PHI Protection:
           - NEVER display raw PHI data in outputs
           - Use de-identified patient references (Patient A, Patient B)
           - Replace specific dates with relative timeframes
           - Mask all direct identifiers per HIPAA Safe Harbor

        2. Access Controls:
           - Verify user authorization before PHI access
           - Log all PHI access attempts with timestamp
           - Enforce session timeouts after 30 minutes
           - Require multi-factor authentication

        3. Data Security:
           - Ensure all PHI is encrypted at rest and in transit
           - Use only secure, HIPAA-compliant communication channels
           - Implement audit logging for all operations
           - Never store PHI in temporary files or caches

        4. Minimum Necessary Standard:
           - Access only PHI necessary for the specific task
           - Limit data processing to essential clinical elements
           - Request additional authorization for expanded access

        5. Incident Response:
           - Report any suspected PHI breaches immediately
           - Document unauthorized access attempts
           - Preserve audit trails for investigation

        CLINICAL PROCESSING GUIDELINES:
        - Focus on medical necessity and clinical relevance
        - Use evidence-based clinical reasoning
        - Provide structured clinical assessments
        - Include compliance verification in all outputs

        DE-IDENTIFICATION REQUIREMENTS:
        - Replace names with generic identifiers
        - Convert specific dates to age ranges or relative dates
        - Mask medical record numbers and identifiers
        - Use general geographic regions instead of specific addresses

        OUTPUT FORMAT:
        All outputs must include:
        1. De-identified clinical summary
        2. Evidence-based recommendations
        3. HIPAA compliance verification statement
        4. Audit log reference number

        PROHIBITED ACTIONS:
        - Including patient names, SSNs, or addresses in outputs
        - Storing PHI in system logs or temporary files
        - Transmitting PHI over unsecured channels
        - Processing PHI without proper authorization

        Always prioritize patient privacy and HIPAA compliance.
    provides:
      - useAs: system_prompt
        in: hipaa-agent
        description: HIPAA compliance instructions

  - id: hipaa-agent
    type: genesis:agent
    name: HIPAA Compliant Healthcare Agent
    description: Secure healthcare data processing with full HIPAA compliance
    config:
      agent_llm: Azure OpenAI
      model_name: gpt-4
      temperature: 0.1
      max_tokens: 3000
      handle_parsing_errors: true
      max_iterations: 5
      verbose: false
    provides:
      - in: deidentification-processor
        useAs: input
        description: Send data for de-identification

  - id: deidentification-processor
    type: genesis:agent
    name: PHI De-identification Processor
    description: Automatic de-identification of PHI data
    config:
      system_prompt: |
        You are a PHI de-identification specialist. Your role is to ensure all outputs are fully de-identified per HIPAA Safe Harbor requirements.

        De-identification Checklist:
        □ Remove all names and replace with generic identifiers
        □ Convert specific dates to relative timeframes
        □ Mask all numeric identifiers (SSN, MRN, account numbers)
        □ Replace specific addresses with general regions
        □ Remove phone numbers, email addresses, URLs
        □ Replace device identifiers with generic references
        □ Verify no biometric identifiers remain
        □ Check for indirect identifiers that could enable re-identification

        Quality Assurance:
        - Maintain clinical utility of de-identified data
        - Preserve temporal relationships where possible
        - Ensure consistency across related records
        - Document de-identification methods used

        Generate a compliance verification statement for each de-identified output.
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: secure-output
        useAs: input
        description: Send de-identified data

  - id: compliance-monitor
    type: genesis:agent
    name: HIPAA Compliance Monitor
    description: Real-time compliance monitoring and reporting
    config:
      system_prompt: |
        Monitor and verify HIPAA compliance for all healthcare data processing.

        Compliance Verification Checklist:
        □ User authorization validated
        □ PHI access properly logged
        □ Data encryption confirmed
        □ De-identification completed
        □ Audit trail preserved
        □ Session security maintained

        Generate compliance verification report for each transaction.
      temperature: 0.1
      max_tokens: 1000
    provides:
      - in: secure-output
        useAs: input
        description: Send compliance verification

  - id: secure-output
    type: genesis:chat_output
    name: HIPAA Compliant Output
    description: Secure, de-identified healthcare information output
    config:
      should_store_message: false  # Don't store PHI in message history

# Sample inputs and outputs
sampleInput:
  patient_query: "Analyze patient data for treatment recommendations"
  authorization_level: "clinical_staff"
  access_purpose: "treatment_planning"

outputs:
  - deidentified_clinical_summary
  - evidence_based_recommendations
  - compliance_verification_report
  - audit_reference_number

# Classification tags
tags:
  - hipaa-compliant
  - healthcare
  - phi-processing
  - clinical-workflow
  - security-enhanced
```

## Compliance Checklist

### Pre-Deployment Validation

- [ ] **Security Metadata**: All healthcare agents include required security classifications
- [ ] **Access Controls**: Role-based access controls properly configured
- [ ] **Encryption**: PHI data encrypted at rest and in transit
- [ ] **Audit Logging**: Comprehensive audit logging enabled
- [ ] **De-identification**: Automatic PHI de-identification implemented
- [ ] **Session Security**: Session timeouts and security measures configured
- [ ] **Incident Response**: Breach detection and response procedures in place
- [ ] **Business Associate Agreements**: All vendor BAAs executed
- [ ] **Staff Training**: HIPAA training completed for all users
- [ ] **Risk Assessment**: Comprehensive risk assessment completed

### Ongoing Compliance Monitoring

- [ ] **Daily**: Review access logs and security alerts
- [ ] **Weekly**: Validate encryption status and user permissions
- [ ] **Monthly**: Generate compliance reports and assessments
- [ ] **Quarterly**: Update risk assessments and security reviews
- [ ] **Annually**: Comprehensive HIPAA compliance audit

## Support Resources

### Regulatory References
- **HIPAA Privacy Rule**: 45 CFR Parts 160 and 164
- **HIPAA Security Rule**: 45 CFR Part 164, Subparts A and C
- **Breach Notification Rule**: 45 CFR Part 164, Subpart D
- **HHS HIPAA Guidelines**: https://www.hhs.gov/hipaa/

### Technical Standards
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework
- **NIST 800-66**: Security Controls for HIPAA
- **IHE Profiles**: Healthcare interoperability standards

### Training Resources
- **HHS HIPAA Training**: https://www.hhs.gov/hipaa/for-professionals/training/
- **AHIMA HIPAA Resources**: https://ahima.org/topics/hipaa/
- **Healthcare Security Awareness**: Security training for healthcare workers

For additional guidance on implementing specific healthcare workflows, see the [Clinical Workflow Creation Guide](clinical-workflow.md) and [Healthcare Integration Guide](healthcare-integration.md).