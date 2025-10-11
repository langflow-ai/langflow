# Post-Visit Q&A Agent - Usage Guide

## Overview
The Post-Visit Q&A Agent helps patients understand their visit documentation by answering questions about medications, care instructions, and follow-up requirements using actual visit notes and discharge summaries.

## Agent Configuration

### Basic Usage
```yaml
# Input: Patient question about their visit
{
  "patient_id": "P123456789",
  "visit_id": "V789012345",
  "question": "When should I take my new medication?",
  "visit_date": "2024-03-15"
}
```

### Configuration Options
- **Temperature**: 0.2 (balanced accuracy and empathy)
- **Max Tokens**: 500 (patient-friendly response length)
- **Model**: GPT-4 (medical accuracy required)
- **Tools**: EHR access, medication database, clinical guidelines

## Use Cases

### 1. Medication Questions
**Patient Question**: "I forgot - when am I supposed to take my blood pressure medicine?"

**Sample Input**:
```json
{
  "patient_id": "P123456789",
  "visit_id": "V789012345",
  "question": "When should I take my new blood pressure medication?",
  "visit_date": "2024-03-15"
}
```

**Sample Output**:
```json
{
  "answer": "Based on your visit with Dr. Smith on March 15th, you should take your new blood pressure medication (Lisinopril 10mg) once daily in the morning with food. Dr. Smith specifically recommended taking it with breakfast to help you remember and reduce any potential stomach upset.",
  "sources": ["Visit notes 3/15/24", "Prescription #RX789456"],
  "confidence": 0.95,
  "follow_up_recommended": false
}
```

### 2. Care Instructions
**Patient Question**: "How should I care for my wound?"

**Sample Output**:
```json
{
  "answer": "According to your discharge instructions, clean the wound gently with soap and water daily, apply the antibiotic ointment Dr. Johnson prescribed, and cover with a clean bandage. Watch for signs of infection like increased redness, warmth, or pus, and call the office if you notice these symptoms.",
  "sources": ["Discharge summary 3/15/24", "Wound care instructions"],
  "confidence": 0.92,
  "follow_up_recommended": false
}
```

### 3. Follow-up Clarity
**Patient Question**: "When do I need to come back for my check-up?"

**Sample Output**:
```json
{
  "answer": "Your follow-up appointment is scheduled for April 1st at 2:00 PM with Dr. Smith. This was arranged during your visit to check on your blood pressure medication response and review your lab results. Please bring your blood pressure log that we discussed.",
  "sources": ["Visit notes 3/15/24", "Appointment scheduling"],
  "confidence": 0.98,
  "follow_up_recommended": false
}
```

### 4. Symptom Concerns
**Patient Question**: "Is it normal to feel dizzy with this new medication?"

**Sample Output**:
```json
{
  "answer": "Dr. Smith mentioned that some dizziness might occur when starting Lisinopril, especially when standing up quickly. This usually improves as your body adjusts to the medication. However, if the dizziness is severe or doesn't improve after a few days, please call our office. Stand up slowly and stay hydrated to help minimize this effect.",
  "sources": ["Visit notes 3/15/24", "Medication counseling notes"],
  "confidence": 0.89,
  "follow_up_recommended": true
}
```

## Integration Examples

### Patient Portal Integration
```javascript
// Example API call from patient portal
const response = await fetch('/api/agents/post-visit-qa', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    patient_id: currentPatient.id,
    visit_id: latestVisit.id,
    question: userQuestion,
    visit_date: latestVisit.date
  })
});

const answer = await response.json();
displayAnswer(answer.answer, answer.sources);
```

### Call Center Integration
```python
# Example integration for call center agents
def get_visit_answer(patient_id, question, visit_id=None):
    payload = {
        "patient_id": patient_id,
        "question": question,
        "visit_id": visit_id or get_latest_visit(patient_id),
        "visit_date": get_visit_date(visit_id)
    }

    response = post_visit_qa_agent.process(payload)

    return {
        "answer": response["answer"],
        "confidence": response["confidence"],
        "should_escalate": response["follow_up_recommended"]
    }
```

## Performance Monitoring

### Key Metrics
- **Response Accuracy**: Target 95% (measured against provider review)
- **Patient Satisfaction**: Target 4.5/5 (post-interaction survey)
- **Follow-up Call Reduction**: Target 30% decrease
- **Response Time**: Target <3 seconds

### Quality Assurance
```yaml
# Sample QA checklist
quality_checks:
  - answer_references_actual_visit: true
  - uses_patient_friendly_language: true
  - includes_specific_medication_details: true
  - appropriate_urgency_assessment: true
  - sources_cited: true
```

## Error Handling

### Common Issues
1. **Visit not found**: Returns guidance to contact office
2. **Incomplete documentation**: Requests specific information
3. **Complex medical question**: Recommends provider contact
4. **Urgent symptom**: Immediately recommends calling office

### Sample Error Response
```json
{
  "answer": "I don't have enough information about your specific visit to answer this question safely. Please call our office at (555) 123-4567 so we can review your records and provide accurate guidance.",
  "sources": [],
  "confidence": 0.0,
  "follow_up_recommended": true,
  "error_type": "insufficient_data"
}
```

## Best Practices

### Implementation Guidelines
1. **Always verify patient identity** before providing visit information
2. **Include clear source citations** for all medical information
3. **Set appropriate confidence thresholds** for medical advice
4. **Escalate complex questions** to human providers
5. **Monitor patient satisfaction** and adjust responses accordingly

### Security Considerations
- HIPAA compliant data access
- Audit logging for all patient interactions
- Secure transmission of medical information
- Access controls based on patient consent

## Troubleshooting

### Common Configuration Issues
- **Missing EHR access**: Verify API credentials and permissions
- **Medication database timeout**: Check connection settings
- **Low confidence scores**: Review prompt template and training data

### Performance Optimization
- Cache frequently accessed visit data
- Pre-process common medication information
- Use batch processing for multiple questions
- Monitor API rate limits for external tools