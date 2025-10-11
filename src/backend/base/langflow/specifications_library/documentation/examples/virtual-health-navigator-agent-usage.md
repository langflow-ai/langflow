# Virtual Health Navigator Agent - Usage Guide

## Overview

The Virtual Health Navigator Agent is an intelligent healthcare triage and navigation system that guides patients to the most appropriate care settings using comprehensive symptom analysis, claims history, and insurance plan rules. It combines clinical expertise with cost optimization to reduce unnecessary healthcare visits while improving patient satisfaction and outcomes.

**Specification Location**: `agents/patient-experience/virtual-health-navigator-agent.yaml`

## Key Capabilities

### 🩺 Advanced Symptom Assessment and Clinical Triage
- Comprehensive symptom evaluation with severity, timing, and pattern analysis
- Evidence-based clinical decision rules for accurate triage
- Emergency condition identification with immediate escalation protocols
- Multi-symptom analysis with differential diagnosis considerations
- Patient demographic and comorbidity risk stratification

### 📊 Personalized Healthcare Claims Pattern Analysis
- Historical healthcare utilization pattern recognition
- Previous care setting effectiveness and outcome tracking
- Seasonal and recurring condition identification
- Provider relationship and specialist consultation history
- Cost analysis and insurance utilization optimization

### 💰 Insurance-Informed Cost-Conscious Navigation
- Real-time benefits verification and coverage determination
- Comprehensive cost estimation including copays and deductibles
- Prior authorization requirement identification
- In-network provider optimization for cost minimization
- Transparent financial responsibility communication

### 🏥 Intelligent Provider Matching and Coordination
- Provider specialty matching with clinical expertise requirements
- Geographic proximity and transportation accessibility optimization
- Real-time availability coordination with appointment scheduling
- Provider rating and patient satisfaction integration
- Cultural competency and language preference matching

### 📚 Empowering Patient Education and Communication
- Clear, empathetic medical recommendation explanations
- Condition-specific patient education and self-care guidance
- Cultural sensitivity and accessibility accommodation
- Anxiety reduction through compassionate communication
- Informed decision-making support with comprehensive information

## Architecture

**Pattern**: Multi-Tool Agent (8 components)
**Complexity**: Complex
**Processing Model**: Single agent with 6 specialized tools

```
Input → Navigator Agent ← Navigation Prompt
          ↑           ↓
     [6 Tools]     Output
     - Symptom Checker API
     - Claims Database
     - Plan Rules Engine
     - Patient Feedback System
     - Facility Directory
     - ML Analytics Engine
```

## Usage Examples

### Example 1: High-Risk Chest Pain Navigation

#### Input Request
```json
{
  "patient_id": "P123456789",
  "symptoms": [
    {
      "symptom": "chest pain",
      "severity": 7,
      "duration": "30 minutes",
      "onset": "sudden"
    },
    {
      "symptom": "shortness of breath",
      "severity": 6,
      "duration": "30 minutes",
      "onset": "sudden"
    }
  ],
  "patient_demographics": {
    "age": 45,
    "gender": "male",
    "chronic_conditions": ["hypertension", "diabetes_type2"],
    "current_medications": ["metformin", "lisinopril"]
  },
  "insurance_info": {
    "plan_id": "BCBS_PPO_2024",
    "member_id": "M987654321",
    "group_number": "GRP12345"
  },
  "urgency_level": "high",
  "preferred_location": {
    "zip_code": "90210",
    "max_distance_miles": 15
  },
  "communication_preferences": {
    "language": "english",
    "accessibility_needs": []
  }
}
```

#### Agent Processing Flow
1. **Symptom Analysis**: Identifies high-risk cardiac presentation requiring immediate evaluation
2. **Claims History**: Reviews previous cardiac workups and specialist relationships
3. **Plan Rules**: Verifies emergency coverage and calculates costs
4. **Provider Matching**: Identifies nearest emergency departments with cardiac capabilities
5. **Safety Protocols**: Triggers immediate escalation for potential cardiac event
6. **Patient Education**: Provides clear emergency instructions and expectations

#### Expected Output
```json
{
  "navigation_recommendation": {
    "recommended_care_setting": "emergency_room",
    "rationale": "Acute chest pain with cardiac risk factors (age 45, male, hypertension, diabetes) combined with shortness of breath requires immediate cardiac evaluation to rule out acute coronary syndrome or other life-threatening conditions.",
    "urgency_level": "urgent",
    "estimated_cost": {
      "copay": 150.00,
      "deductible_impact": 500.00,
      "total_estimate": 2500.00
    }
  },
  "provider_recommendations": [
    {
      "provider_name": "Cedars-Sinai Medical Center",
      "facility_name": "Emergency Department",
      "address": "8700 Beverly Blvd, Los Angeles, CA 90048",
      "phone": "+1-310-423-3277",
      "distance_miles": 3.2,
      "availability": "immediate",
      "in_network": true,
      "specialty_match": 0.95
    }
  ],
  "symptom_analysis": {
    "primary_concern": "Possible acute coronary syndrome",
    "severity_assessment": "high_risk_cardiac",
    "potential_conditions": [
      "Acute coronary syndrome",
      "Unstable angina",
      "Myocardial infarction",
      "Pulmonary embolism"
    ],
    "red_flags": [
      "Chest pain in diabetic male over 40",
      "Associated shortness of breath",
      "Sudden onset symptoms"
    ]
  },
  "next_steps": [
    "Go to emergency department immediately - do not drive yourself",
    "Bring list of current medications and insurance card",
    "Call 911 if symptoms worsen during transport",
    "Chew aspirin (if not allergic) while en route unless contraindicated"
  ],
  "follow_up_schedule": {
    "check_in_hours": 2,
    "escalation_triggers": [
      "Worsening chest pain",
      "New onset weakness or numbness",
      "Fainting or near-fainting"
    ]
  }
}
```

### Example 2: Minor Cold Symptoms Navigation

#### Input Request
```json
{
  "patient_id": "P987654321",
  "symptoms": [
    {
      "symptom": "runny nose",
      "severity": 3,
      "duration": "2 days",
      "onset": "gradual"
    },
    {
      "symptom": "mild sore throat",
      "severity": 2,
      "duration": "1 day",
      "onset": "gradual"
    },
    {
      "symptom": "low-grade fever",
      "severity": 2,
      "duration": "1 day",
      "onset": "gradual"
    }
  ],
  "patient_demographics": {
    "age": 28,
    "gender": "female",
    "chronic_conditions": [],
    "current_medications": []
  },
  "insurance_info": {
    "plan_id": "AETNA_HMO_2024",
    "member_id": "M123456789",
    "group_number": "GRP67890"
  },
  "urgency_level": "low",
  "preferred_location": {
    "zip_code": "10001",
    "max_distance_miles": 10
  },
  "communication_preferences": {
    "language": "english",
    "accessibility_needs": []
  }
}
```

#### Agent Processing Flow
1. **Symptom Analysis**: Identifies viral upper respiratory infection pattern
2. **Claims History**: Reviews previous cold/flu patterns and preferred treatments
3. **Plan Rules**: Evaluates telemedicine coverage and self-care options
4. **Cost Optimization**: Recommends most cost-effective appropriate care
5. **Patient Education**: Provides comprehensive self-care guidance
6. **Follow-up Planning**: Sets monitoring protocols for symptom progression

#### Expected Output
```json
{
  "navigation_recommendation": {
    "recommended_care_setting": "telemedicine",
    "rationale": "Mild viral upper respiratory symptoms in healthy young adult can be effectively managed through telemedicine consultation with self-care guidance, avoiding unnecessary in-person visits and reducing costs.",
    "urgency_level": "low",
    "estimated_cost": {
      "copay": 25.00,
      "deductible_impact": 0.00,
      "total_estimate": 75.00
    }
  },
  "provider_recommendations": [
    {
      "provider_name": "Dr. Sarah Johnson, MD",
      "facility_name": "Virtual Care Center",
      "address": "Telemedicine Platform",
      "phone": "+1-800-TELEMD",
      "distance_miles": 0,
      "availability": "within 30 minutes",
      "in_network": true,
      "specialty_match": 0.85
    }
  ],
  "symptom_analysis": {
    "primary_concern": "Viral upper respiratory infection",
    "severity_assessment": "mild_self_limiting",
    "potential_conditions": [
      "Common cold",
      "Viral rhinitis",
      "Mild viral pharyngitis"
    ],
    "red_flags": []
  },
  "next_steps": [
    "Schedule telemedicine appointment for symptom assessment",
    "Continue self-care measures: rest, fluids, throat lozenges",
    "Monitor temperature and symptom progression",
    "Over-the-counter medications as needed for comfort"
  ],
  "follow_up_schedule": {
    "check_in_hours": 48,
    "escalation_triggers": [
      "Fever above 101.5°F",
      "Severe sore throat or difficulty swallowing",
      "Shortness of breath or chest pain",
      "Symptoms worsen after 5 days"
    ]
  }
}
```

### Example 3: Chronic Condition Management Navigation

#### Input Request
```json
{
  "patient_id": "P456789123",
  "symptoms": [
    {
      "symptom": "increased fatigue",
      "severity": 5,
      "duration": "1 week",
      "onset": "gradual"
    },
    {
      "symptom": "increased thirst",
      "severity": 4,
      "duration": "1 week",
      "onset": "gradual"
    },
    {
      "symptom": "frequent urination",
      "severity": 4,
      "duration": "1 week",
      "onset": "gradual"
    }
  ],
  "patient_demographics": {
    "age": 52,
    "gender": "male",
    "chronic_conditions": ["diabetes_type2", "hypertension"],
    "current_medications": ["metformin", "glipizide", "lisinopril"]
  },
  "insurance_info": {
    "plan_id": "MEDICARE_ADVANTAGE_2024",
    "member_id": "M456789123",
    "group_number": "MEDICARE"
  },
  "urgency_level": "moderate",
  "preferred_location": {
    "zip_code": "33101",
    "max_distance_miles": 20
  },
  "communication_preferences": {
    "language": "spanish",
    "accessibility_needs": ["wheelchair_accessible"]
  }
}
```

#### Expected Output
```json
{
  "navigation_recommendation": {
    "recommended_care_setting": "primary_care",
    "rationale": "Classic symptoms of uncontrolled diabetes in established diabetic patient require prompt primary care evaluation for medication adjustment and glycemic control optimization. Not emergent but should be addressed within 24-48 hours.",
    "urgency_level": "moderate",
    "estimated_cost": {
      "copay": 30.00,
      "deductible_impact": 0.00,
      "total_estimate": 200.00
    }
  },
  "provider_recommendations": [
    {
      "provider_name": "Dr. Maria Rodriguez, MD - Endocrinology",
      "facility_name": "Miami Diabetes Center",
      "address": "1200 Biscayne Blvd, Miami, FL 33132",
      "phone": "+1-305-555-0123",
      "distance_miles": 4.5,
      "availability": "next day appointment",
      "in_network": true,
      "specialty_match": 0.98
    }
  ],
  "next_steps": [
    "Schedule appointment with endocrinologist within 48 hours",
    "Check blood glucose levels and record readings",
    "Review current medication adherence and timing",
    "Bring glucose log and medication list to appointment"
  ]
}
```

## Configuration Variables

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `llm_provider` | string | Azure OpenAI | LLM provider for navigation logic |
| `model_name` | string | gpt-4 | Model for symptom analysis and recommendations |
| `temperature` | float | 0.2 | Balanced temperature for empathetic yet accurate responses |
| `max_tokens` | integer | 2000 | Maximum tokens for comprehensive guidance |
| `symptom_severity_threshold` | float | 0.7 | Threshold for urgent care recommendations |
| `emergency_keywords_enabled` | boolean | true | Enable immediate emergency detection |
| `claims_history_lookback_months` | integer | 24 | Months of claims history to analyze |
| `enable_patient_feedback_collection` | boolean | true | Enable post-navigation feedback |
| `preferred_care_radius_miles` | integer | 25 | Radius for care facility recommendations |

## Key Performance Indicators

### Quality Metrics
- **Care Setting Recommendation Accuracy**: Target 92%
- **Patient Satisfaction Rate**: Target 88%
- **Provider Recommendation Accuracy**: Target 90%
- **Emergency Condition Detection Rate**: Target 98%
- **Insurance Coverage Accuracy**: Target 96%

### Performance Metrics
- **Average Navigation Time**: Target 180 seconds
- **Successful Care Setting Navigation Rate**: Target 94%

### Outcome Metrics
- **Reduction in Unnecessary Hospital Visits**: Target 35%
- **Cost Savings Per Navigation**: Target $150
- **Patient Follow-up Compliance**: Target 78%

## Tool Integration Details

### Symptom Checker API Engine
- **Purpose**: AI-powered clinical assessment and triage
- **Capabilities**: Multi-symptom analysis, differential diagnosis, risk stratification
- **Features**: Evidence-based protocols, red flag detection, safety protocols

### Healthcare Claims Analytics Database
- **Purpose**: Patient history analysis for personalized navigation
- **Capabilities**: Utilization patterns, provider relationships, cost analysis
- **Features**: 24-month lookback, outcome tracking, pattern recognition

### Insurance Plan Rules Engine
- **Purpose**: Real-time benefits verification and cost optimization
- **Capabilities**: Coverage determination, cost calculation, authorization requirements
- **Features**: Multi-plan comparison, network adequacy, financial transparency

### Patient Feedback Analytics System
- **Purpose**: Navigation quality improvement and satisfaction tracking
- **Capabilities**: Outcome tracking, satisfaction measurement, quality metrics
- **Features**: Multi-modal collection, real-time analytics, improvement insights

### Healthcare Facility Directory
- **Purpose**: Comprehensive provider and facility matching
- **Capabilities**: Real-time availability, quality ratings, accessibility information
- **Features**: Geographic optimization, insurance verification, cultural competency

### ML Analytics Engine
- **Purpose**: Personalized navigation optimization and outcome prediction
- **Capabilities**: Pattern recognition, outcome prediction, continuous improvement
- **Features**: Patient profiling, satisfaction prediction, cost optimization

## Care Setting Decision Matrix

### Emergency Room
**Indications**: Life-threatening conditions, severe trauma, cardiac events, stroke symptoms, severe breathing difficulties
**Examples**: Chest pain with cardiac risk factors, severe head trauma, difficulty breathing, loss of consciousness

### Urgent Care
**Indications**: Non-emergent urgent needs, minor injuries, infections, after-hours care
**Examples**: Minor fractures, lacerations requiring stitches, ear infections, strep throat

### Primary Care
**Indications**: Routine health concerns, chronic disease management, preventive care
**Examples**: Annual physicals, medication refills, chronic condition monitoring, health screenings

### Specialist Care
**Indications**: Condition-specific expertise, complex diagnoses, referral-based care
**Examples**: Cardiology consultation, dermatology evaluation, orthopedic assessment

### Telemedicine
**Indications**: Remote consultations, follow-ups, medication management, minor symptoms
**Examples**: Cold symptoms, medication adjustments, mental health counseling, chronic disease monitoring

### Self-Care
**Indications**: Minor symptoms manageable at home with guidance
**Examples**: Minor colds, headaches, muscle strains, minor skin conditions

### Pharmacy Care
**Indications**: Over-the-counter treatable conditions, medication consultations
**Examples**: Minor allergies, minor pain relief, immunizations, medication questions

## Safety and Escalation Protocols

### Immediate Emergency Escalation
**Triggers**: Chest pain with cardiac risk factors, difficulty breathing, severe abdominal pain, neurological symptoms, severe trauma, loss of consciousness
**Actions**: Direct to emergency department, provide 911 instructions, immediate follow-up protocols

### Urgent Care Escalation
**Triggers**: Moderate to severe symptoms requiring same-day evaluation
**Actions**: Schedule urgent care within 4-6 hours, provide symptom monitoring instructions

### Follow-up Monitoring
**Triggers**: Symptoms requiring observation and potential escalation
**Actions**: Schedule check-ins, provide clear escalation triggers, symptom diary instructions

## Patient Communication Excellence

### Empathetic Communication Principles
- Use compassionate, non-judgmental language that reduces anxiety
- Acknowledge patient concerns and validate healthcare experiences
- Maintain cultural sensitivity and accommodate language preferences
- Ensure accessibility for patients with disabilities or special needs

### Clear Medical Communication
- Explain medical terminology in patient-friendly language
- Provide specific, actionable recommendations with clear next steps
- Set realistic expectations for treatment timelines and outcomes
- Offer condition-specific education and self-care guidance

### Anxiety Reduction Strategies
- Provide reassurance when clinically appropriate
- Explain rationale behind care setting recommendations
- Offer multiple care options when safe and appropriate
- Share success stories and positive outcome expectations

## Cost Optimization Strategies

### Insurance-Informed Decision Making
- Always verify coverage before recommending care settings
- Calculate and communicate estimated patient financial responsibility
- Prioritize in-network providers and facilities
- Identify most cost-effective clinically appropriate options

### Care Setting Cost Hierarchy
1. **Self-Care** (lowest cost): Home management with OTC medications
2. **Telemedicine** (low cost): Virtual consultations and remote monitoring
3. **Pharmacy Care** (low cost): OTC consultations and minor treatments
4. **Primary Care** (moderate cost): Routine and preventive care
5. **Urgent Care** (moderate cost): Non-emergent urgent conditions
6. **Specialist Care** (higher cost): Specialized evaluation and treatment
7. **Emergency Room** (highest cost): Life-threatening and severe conditions

## Quality Assurance Standards

### Clinical Safety Standards
- Maintain conservative triage decisions for patient safety
- Validate all recommendations against current medical guidelines
- Provide clear escalation pathways for worsening symptoms
- Document rationale for all care setting recommendations

### Navigation Accuracy Standards
- Ensure provider recommendations match patient clinical needs
- Verify insurance coverage and cost estimates accuracy
- Confirm appointment availability and accessibility requirements
- Track patient outcomes and satisfaction for continuous improvement

## Use Cases and Scenarios

### Primary Use Cases
1. **Symptom Triage and Navigation**: Guiding patients to appropriate care settings based on symptom presentation
2. **Cost-Conscious Healthcare Navigation**: Optimizing care recommendations for insurance coverage and cost
3. **Emergency Condition Detection**: Identifying life-threatening conditions requiring immediate attention
4. **Chronic Disease Management**: Supporting ongoing care coordination for established conditions

### Advanced Scenarios
1. **Multi-Symptom Complex Presentations**: Managing patients with multiple concurrent symptoms
2. **Chronic Disease Exacerbations**: Recognizing when stable conditions require immediate attention
3. **Mental Health Integration**: Incorporating psychological symptoms into navigation decisions
4. **Pediatric and Geriatric Considerations**: Age-specific navigation protocols and safety measures

### Special Populations
1. **High-Risk Patients**: Enhanced monitoring for patients with multiple comorbidities
2. **Non-English Speaking Patients**: Language-appropriate navigation and provider matching
3. **Patients with Disabilities**: Accessibility-focused provider and facility recommendations
4. **Rural Patients**: Distance-optimized care recommendations with telemedicine emphasis

## Integration Guidelines

### Prerequisites
- Symptom checker API with clinical decision support capabilities
- Healthcare claims database with patient history access
- Insurance plan rules engine with real-time benefits verification
- Patient feedback system with satisfaction tracking
- Healthcare facility directory with real-time availability
- Machine learning analytics platform with personalization capabilities

### Implementation Steps
1. Configure tool credentials and API access for all integrated systems
2. Set up patient safety protocols and emergency escalation procedures
3. Define clinical decision rules and triage algorithms
4. Implement cost optimization logic with insurance integration
5. Create patient communication templates and multilingual support
6. Establish quality metrics tracking and continuous improvement processes

### Best Practices
- Regularly update clinical protocols and evidence-based guidelines
- Monitor patient outcomes and satisfaction metrics continuously
- Maintain cultural competency and accessibility standards
- Ensure HIPAA compliance and patient privacy protection
- Implement robust safety nets for high-risk symptom presentations
- Provide comprehensive staff training on navigation protocols and escalation procedures

---

*This usage guide provides comprehensive instructions for implementing and operating the Virtual Health Navigator Agent effectively in healthcare environments to improve patient outcomes while reducing costs and enhancing satisfaction.*