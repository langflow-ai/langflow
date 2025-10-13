# Appointment Concierge Agent - Usage Guide

## Overview

The Appointment Concierge Agent automates comprehensive appointment scheduling with intelligent EHR integration, real-time insurance eligibility verification, and multi-channel patient communication. It provides a complete concierge service experience for healthcare appointment management.

**Specification Location**: `agents/patient-experience/appointment-concierge-agent.yaml`

## Key Capabilities

### 🏥 Intelligent Scheduling Coordination
- Real-time provider calendar access and availability checking
- Multi-provider appointment coordination
- Location and specialty optimization
- Conflict resolution and rescheduling management

### 💳 Real-Time Insurance Verification
- Instant eligibility status checking
- Coverage verification for specific appointment types
- Prior authorization requirement identification
- Copay and deductible calculation
- Out-of-network penalty assessment

### 📍 Location and Provider Optimization
- Provider matching by specialty, insurance acceptance, and location
- Travel distance and convenience optimization
- Availability-based scheduling recommendations
- Preferred location matching within radius settings

### 📱 Multi-Channel Patient Communication
- SMS appointment confirmations and reminders
- Email confirmations with calendar attachments
- Facility information and preparation instructions
- Customized messaging based on appointment type

### 📊 Analytics and Performance Tracking
- Scheduling success rate monitoring
- Patient satisfaction tracking
- No-show rate analysis
- Communication effectiveness metrics

## Architecture

**Pattern**: Multi-Tool Agent (7 components)
**Complexity**: Complex
**Processing Model**: Single agent with 5 specialized tools

```
Input → Concierge Agent ← Scheduling Prompt
          ↑          ↓
     [5 Tools]    Output
     - EHR Calendar
     - Insurance API
     - SMS Service
     - Email Service
     - Analytics
```

## Usage Examples

### Example 1: Routine Annual Physical Scheduling

#### Input Request
```json
{
  "patient_id": "P123456789",
  "appointment_type": "annual_physical",
  "preferred_dates": ["2024-04-15", "2024-04-16", "2024-04-17"],
  "preferred_times": ["morning", "afternoon"],
  "preferred_locations": ["Downtown Clinic", "Westside Medical Center"],
  "insurance_info": {
    "plan_id": "BCBS_PPO_2024",
    "member_id": "M987654321",
    "group_number": "GRP12345"
  },
  "contact_preferences": {
    "phone": "+1-555-123-4567",
    "email": "patient@email.com",
    "sms_enabled": true,
    "email_enabled": true
  },
  "urgency_level": "routine"
}
```

#### Agent Processing Flow
1. **Insurance Verification**: Confirms BCBS PPO eligibility and $35 copay
2. **Provider Matching**: Finds primary care physicians accepting BCBS at preferred locations
3. **Schedule Optimization**: Identifies available slots matching patient preferences
4. **Appointment Booking**: Reserves April 16, 10:00 AM at Downtown Clinic
5. **Multi-Channel Communication**: Sends SMS and email confirmations
6. **Reminder Setup**: Schedules 24-hour advance reminder

#### Expected Output
```json
{
  "appointment_details": {
    "appointment_id": "APPT-2024-0416-001",
    "scheduled_date": "2024-04-16",
    "scheduled_time": "10:00 AM",
    "provider_name": "Dr. Sarah Johnson, MD",
    "facility_location": "Downtown Clinic",
    "duration_minutes": 60
  },
  "insurance_verification": {
    "eligibility_confirmed": true,
    "coverage_details": {
      "service_covered": true,
      "in_network": true
    },
    "copay_amount": 35.00,
    "authorization_required": false
  },
  "notifications_sent": {
    "sms_confirmation": true,
    "email_confirmation": true,
    "reminder_scheduled": true
  },
  "next_steps": [
    "Bring insurance card and photo ID to appointment",
    "Complete patient forms online 24 hours before visit",
    "Fast for 12 hours before appointment for lab work"
  ]
}
```

### Example 2: Urgent Specialist Consultation

#### Input Request
```json
{
  "patient_id": "P987654321",
  "appointment_type": "cardiology_consultation",
  "preferred_dates": ["2024-04-12", "2024-04-13"],
  "preferred_times": ["any"],
  "preferred_locations": ["any"],
  "insurance_info": {
    "plan_id": "AETNA_HMO_2024",
    "member_id": "M123456789",
    "group_number": "GRP67890"
  },
  "contact_preferences": {
    "phone": "+1-555-987-6543",
    "email": "urgent.patient@email.com",
    "sms_enabled": true,
    "email_enabled": true
  },
  "urgency_level": "urgent"
}
```

#### Agent Processing Flow
1. **Insurance Verification**: Confirms Aetna HMO requires PCP referral
2. **Authorization Check**: Identifies prior authorization requirement
3. **Specialist Search**: Finds in-network cardiologists with urgent availability
4. **Coordination**: Books earliest available slot pending authorization
5. **Communication**: Sends detailed instructions for authorization process

#### Expected Output
```json
{
  "appointment_details": {
    "appointment_id": "APPT-2024-0413-URG",
    "scheduled_date": "2024-04-13",
    "scheduled_time": "2:30 PM",
    "provider_name": "Dr. Michael Chen, MD - Cardiology",
    "facility_location": "Heart Specialists Medical Center",
    "duration_minutes": 90
  },
  "insurance_verification": {
    "eligibility_confirmed": true,
    "coverage_details": {
      "service_covered": true,
      "in_network": true
    },
    "copay_amount": 50.00,
    "authorization_required": true
  },
  "notifications_sent": {
    "sms_confirmation": true,
    "email_confirmation": true,
    "reminder_scheduled": true
  },
  "next_steps": [
    "Contact PCP for specialist referral authorization",
    "Bring EKG and echo results to appointment",
    "Complete cardiac history questionnaire online",
    "Appointment confirmed pending authorization approval"
  ]
}
```

## Configuration Variables

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `llm_provider` | string | Azure OpenAI | LLM provider for scheduling logic |
| `model_name` | string | gpt-4 | Model for complex scheduling decisions |
| `temperature` | float | 0.1 | Low temperature for consistent decisions |
| `scheduling_window_days` | integer | 30 | Default scheduling window |
| `reminder_advance_hours` | integer | 24 | Hours before appointment for reminders |
| `enable_sms_notifications` | boolean | true | Enable SMS notifications |
| `enable_email_notifications` | boolean | true | Enable email notifications |
| `preferred_location_radius_miles` | integer | 15 | Radius for location matching |

## Key Performance Indicators

### Quality Metrics
- **Appointment Scheduling Success Rate**: Target 95%
- **Insurance Eligibility Confirmation Rate**: Target 98%
- **Preferred Location Match Rate**: Target 85%
- **Patient Satisfaction Score**: Target 4.7/5

### Performance Metrics
- **Average Scheduling Time**: Target 120 seconds
- **Multi-Channel Communication Success**: Target 96%
- **Insurance Authorization Accuracy**: Target 99%

### Outcome Metrics
- **Appointment No-Show Rate**: Target <8%

## Tool Integration Details

### EHR Calendar API Integration
- **Purpose**: Real-time provider availability and appointment booking
- **Capabilities**: Multi-provider scheduling, conflict resolution, specialty filtering
- **Configuration**: v2 API with provider details and facility information

### Insurance Eligibility API
- **Purpose**: Real-time eligibility verification and benefits checking
- **Standards**: 270 eligibility verification standard
- **Features**: Coverage details, authorization requirements, financial responsibility

### SMS Notification Gateway
- **Provider**: Twilio
- **Features**: HIPAA-compliant messaging, delivery tracking, opt-out handling
- **Message Types**: Confirmations, reminders, instructions, updates

### Email Notification Service
- **Provider**: SendGrid
- **Features**: HTML templates, calendar attachments, engagement analytics
- **Templates**: Handlebars template engine with personalization

### Analytics Tracking Platform
- **Purpose**: Performance monitoring and KPI tracking
- **Metrics**: Success rates, satisfaction scores, no-show analysis
- **Features**: Real-time tracking, dashboard integration, KPI alerting

## Security and Compliance

### Data Protection
- **Visibility**: Private
- **Confidentiality**: High
- **GDPR Sensitive**: Yes
- **HIPAA Compliant**: Yes

### Access Controls
- **Patient Data Access**: Yes (with audit logging)
- **Insurance Data Access**: Yes (encrypted transmission)
- **Communication Tracking**: Yes (for compliance reporting)

## Troubleshooting

### Common Issues

#### Issue: Insurance Verification Fails
**Symptoms**: Cannot confirm eligibility status
**Solutions**:
1. Verify insurance information accuracy
2. Check API connectivity status
3. Retry with manual verification backup
4. Escalate to benefits specialist

#### Issue: No Available Appointments
**Symptoms**: No slots found matching preferences
**Solutions**:
1. Expand date range and location radius
2. Suggest alternative appointment types
3. Offer waitlist registration
4. Provide cancellation notification signup

#### Issue: Authorization Required
**Symptoms**: Prior authorization needed before scheduling
**Solutions**:
1. Provide detailed authorization instructions
2. Schedule provisional appointment pending approval
3. Coordinate with PCP for referral process
4. Track authorization status

### Optimization Tips

1. **Preference Flexibility**: Encourage broader preferences for better matching
2. **Early Scheduling**: Book appointments well in advance for optimal availability
3. **Insurance Updates**: Verify insurance information annually
4. **Communication Preferences**: Maintain updated contact information
5. **Follow-up Coordination**: Use analytics to optimize scheduling patterns

## Use Cases

### Primary Use Cases
1. **Routine Care Scheduling**: Annual physicals, preventive care, follow-ups
2. **Specialist Referrals**: Coordinating specialist consultations with authorization
3. **Urgent Care Scheduling**: Same-day or next-day appointment needs
4. **Multi-Provider Coordination**: Complex care requiring multiple appointments

### Advanced Scenarios
1. **Family Scheduling**: Coordinating appointments for multiple family members
2. **Procedure Scheduling**: Pre-operative appointments with multiple requirements
3. **Telehealth Integration**: Hybrid in-person and virtual appointment coordination
4. **Care Plan Scheduling**: Automated scheduling based on treatment protocols

## Integration Guidelines

### Prerequisites
- EHR system with API access
- Insurance eligibility verification service
- SMS/Email service providers
- Analytics platform integration

### Implementation Steps
1. Configure tool credentials and API access
2. Set up SMS and email templates
3. Define scheduling business rules
4. Test insurance verification workflows
5. Implement analytics tracking
6. Train staff on escalation procedures

### Best Practices
- Regularly update provider and facility information
- Monitor KPIs and adjust configuration variables
- Maintain backup manual processes for system failures
- Keep communication templates updated and personalized
- Regular compliance audits for HIPAA requirements

---

*This usage guide provides comprehensive instructions for implementing and operating the Appointment Concierge Agent effectively in healthcare environments.*