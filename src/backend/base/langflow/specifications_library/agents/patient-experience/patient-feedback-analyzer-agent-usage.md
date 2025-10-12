# Patient Feedback Analyzer Agent - Usage Guide

## Overview
The Patient Feedback Analyzer Agent analyzes call center logs, survey responses, and complaints to extract themes and sentiment, providing actionable insights to improve member experience metrics.

## Agent Configuration

### Basic Usage
```yaml
# Input: Analysis request with parameters
{
  "analysis_type": "comprehensive",
  "date_range": {
    "start_date": "2024-02-01",
    "end_date": "2024-02-29"
  },
  "data_sources": ["call_center", "surveys", "complaints"],
  "filters": {
    "department": "customer_service",
    "service_type": "billing_inquiry"
  }
}
```

### Configuration Options
- **Temperature**: 0.1 (consistent analytical results)
- **Max Tokens**: 3000 (comprehensive analysis)
- **Model**: GPT-4 (complex analytical reasoning)
- **Tools**: Call center API, survey platform, CRM, NLP engine, ML theme extractor

## Use Cases

### 1. Monthly Executive Report
**Purpose**: Comprehensive overview of patient feedback for leadership

**Sample Input**:
```json
{
  "analysis_type": "comprehensive",
  "date_range": {
    "start_date": "2024-02-01",
    "end_date": "2024-02-29"
  },
  "data_sources": ["call_center", "surveys", "complaints"],
  "filters": {}
}
```

**Sample Output**:
```json
{
  "sentiment_analysis": {
    "overall_sentiment": "mixed",
    "sentiment_distribution": {
      "positive": 35,
      "neutral": 30,
      "negative": 35
    },
    "confidence_score": 0.91,
    "emotional_indicators": ["frustration", "satisfaction", "confusion"]
  },
  "themes": [
    {
      "theme": "billing_clarity",
      "frequency": 234,
      "sentiment": "negative",
      "priority": "high",
      "examples": [
        "unexpected charges",
        "confusing statements",
        "billing errors"
      ]
    },
    {
      "theme": "staff_helpfulness",
      "frequency": 189,
      "sentiment": "positive",
      "priority": "medium",
      "examples": [
        "friendly representatives",
        "knowledgeable staff",
        "patient explanations"
      ]
    }
  ],
  "actionable_insights": [
    {
      "insight": "Billing statement confusion is the primary driver of negative feedback (40% of complaints)",
      "priority": "high",
      "recommended_action": "Redesign billing statements with plain language and visual aids",
      "impact_estimate": "25-35% reduction in billing-related calls",
      "timeline": "3 months",
      "department": "billing_operations"
    }
  ]
}
```

### 2. Department-Specific Analysis
**Purpose**: Focus on specific department performance

**Sample Input**:
```json
{
  "analysis_type": "themes",
  "date_range": {
    "start_date": "2024-03-01",
    "end_date": "2024-03-31"
  },
  "data_sources": ["call_center", "complaints"],
  "filters": {
    "department": "clinical_support",
    "priority": "high"
  }
}
```

**Sample Output**:
```json
{
  "themes": [
    {
      "theme": "appointment_scheduling",
      "frequency": 87,
      "sentiment": "negative",
      "priority": "high",
      "examples": [
        "long wait times for appointments",
        "difficulty reaching scheduling",
        "appointment cancellations"
      ]
    },
    {
      "theme": "provider_communication",
      "frequency": 64,
      "sentiment": "mixed",
      "priority": "medium",
      "examples": [
        "rushed consultations",
        "clear explanations appreciated",
        "need more time with doctor"
      ]
    }
  ],
  "actionable_insights": [
    {
      "insight": "Appointment scheduling system creates patient frustration",
      "priority": "high",
      "recommended_action": "Implement online scheduling and improve phone system",
      "impact_estimate": "40% reduction in scheduling complaints",
      "timeline": "6 months",
      "department": "clinical_operations"
    }
  ]
}
```

### 3. Trend Analysis
**Purpose**: Track sentiment and theme changes over time

**Sample Input**:
```json
{
  "analysis_type": "trends",
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-03-31"
  },
  "data_sources": ["surveys", "call_center"],
  "filters": {
    "metric": "patient_satisfaction"
  }
}
```

**Sample Output**:
```json
{
  "trends": {
    "sentiment_trend": "improving_gradually",
    "trend_data": [
      {"month": "2024-01", "sentiment_score": 3.2},
      {"month": "2024-02", "sentiment_score": 3.4},
      {"month": "2024-03", "sentiment_score": 3.7}
    ],
    "emerging_themes": [
      "telehealth_satisfaction",
      "digital_portal_usage",
      "mobile_app_feedback"
    ],
    "improvement_areas": [
      "billing_transparency",
      "wait_time_communication",
      "follow_up_coordination"
    ]
  },
  "actionable_insights": [
    {
      "insight": "Gradual sentiment improvement suggests recent initiatives are working",
      "priority": "medium",
      "recommended_action": "Continue current improvement efforts and accelerate digital initiatives",
      "impact_estimate": "Maintain positive trajectory",
      "timeline": "Ongoing"
    }
  ]
}
```

### 4. Crisis Response Analysis
**Purpose**: Rapid analysis of emerging issues

**Sample Input**:
```json
{
  "analysis_type": "sentiment",
  "date_range": {
    "start_date": "2024-03-15",
    "end_date": "2024-03-22"
  },
  "data_sources": ["call_center", "complaints"],
  "filters": {
    "urgency": "high",
    "sentiment": "negative"
  }
}
```

**Sample Output**:
```json
{
  "sentiment_analysis": {
    "overall_sentiment": "negative",
    "sentiment_distribution": {
      "positive": 10,
      "neutral": 20,
      "negative": 70
    },
    "confidence_score": 0.94,
    "emotional_indicators": ["anger", "frustration", "anxiety"]
  },
  "actionable_insights": [
    {
      "insight": "Sudden spike in negative feedback related to system outage",
      "priority": "critical",
      "recommended_action": "Immediate communication plan and service recovery protocol",
      "impact_estimate": "Prevent further reputation damage",
      "timeline": "Immediate",
      "department": "crisis_management"
    }
  ]
}
```

## Integration Examples

### Dashboard Integration
```javascript
// Example dashboard API integration
async function loadFeedbackAnalysis() {
  const response = await fetch('/api/agents/feedback-analyzer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_type: 'comprehensive',
      date_range: getLastMonth(),
      data_sources: ['call_center', 'surveys', 'complaints']
    })
  });

  const analysis = await response.json();

  updateSentimentChart(analysis.sentiment_analysis);
  updateThemesTable(analysis.themes);
  updateInsights(analysis.actionable_insights);
}
```

### Automated Reporting
```python
# Example automated monthly report generation
def generate_monthly_feedback_report(month, year):
    analysis_request = {
        "analysis_type": "comprehensive",
        "date_range": {
            "start_date": f"{year}-{month:02d}-01",
            "end_date": get_last_day_of_month(year, month)
        },
        "data_sources": ["call_center", "surveys", "complaints"]
    }

    results = feedback_analyzer.process(analysis_request)

    report = {
        "executive_summary": generate_summary(results),
        "key_metrics": extract_metrics(results),
        "priority_actions": results["actionable_insights"][:5],
        "detailed_analysis": results
    }

    return generate_pdf_report(report)
```

### Alert System Integration
```python
# Example alert system for negative sentiment spikes
def monitor_sentiment_alerts():
    weekly_analysis = feedback_analyzer.process({
        "analysis_type": "sentiment",
        "date_range": get_last_week(),
        "data_sources": ["call_center", "complaints"]
    })

    current_negative = weekly_analysis["sentiment_analysis"]["sentiment_distribution"]["negative"]

    if current_negative > NEGATIVE_SENTIMENT_THRESHOLD:
        send_alert({
            "type": "sentiment_spike",
            "severity": "high" if current_negative > 60 else "medium",
            "details": weekly_analysis["actionable_insights"],
            "recipients": ["patient_experience_team", "operations_manager"]
        })
```

## Performance Monitoring

### Key Metrics
- **Analysis Accuracy**: Target 95% (validated against manual review)
- **Insight Actionability**: Target 4.5/5 (stakeholder rating)
- **Theme Extraction Precision**: Target 90%
- **Cross-Source Correlation**: Target 85% success rate
- **Processing Time**: Target <5 seconds for comprehensive analysis

### Quality Assurance
```yaml
# Sample QA validation
quality_checks:
  - sentiment_accuracy_vs_human: >92%
  - theme_relevance_score: >4.0
  - insight_specificity: actionable_and_measurable
  - data_coverage: >95%
  - statistical_significance: validated
```

## Data Source Configuration

### Call Center Integration
```yaml
call_center_config:
  api_endpoint: "https://api.callcenter.com/v1"
  authentication: "bearer_token"
  data_types:
    - call_transcripts
    - satisfaction_scores
    - resolution_status
    - agent_notes
  filters:
    - date_range
    - department
    - call_type
```

### Survey Platform Integration
```yaml
survey_config:
  platforms:
    - qualtrics
    - surveymonkey
    - custom_platform
  survey_types:
    - post_visit_satisfaction
    - nps_surveys
    - experience_surveys
    - hcahps
  data_extraction:
    - structured_responses
    - free_text_comments
    - demographic_data
```

### CRM Complaints Integration
```yaml
crm_config:
  system: "salesforce"
  data_types:
    - formal_complaints
    - grievances
    - resolution_notes
    - follow_up_satisfaction
  categorization:
    - severity_level
    - complaint_type
    - department
    - resolution_status
```

## Error Handling

### Common Issues
1. **Data source unavailable**: Graceful degradation with available sources
2. **Insufficient data**: Clear messaging about sample size limitations
3. **Analysis timeout**: Chunked processing for large datasets
4. **Low confidence scores**: Flag for manual review

### Sample Error Response
```json
{
  "status": "partial_success",
  "analysis_completed": true,
  "warnings": [
    {
      "type": "data_limitation",
      "message": "Survey data unavailable for 3 days in requested range",
      "impact": "Results may not reflect complete picture"
    }
  ],
  "confidence_adjustments": {
    "overall_confidence": 0.87,
    "affected_metrics": ["theme_frequency", "sentiment_distribution"]
  }
}
```

## Best Practices

### Implementation Guidelines
1. **Validate data quality** before analysis
2. **Use statistical significance testing** for trends
3. **Cross-reference insights** across multiple sources
4. **Maintain patient privacy** throughout analysis
5. **Regular model retraining** with new feedback patterns

### Analytics Standards
- Minimum sample size: 100 feedback items for reliable analysis
- Confidence threshold: 85% for actionable insights
- Update frequency: Weekly for trending, monthly for comprehensive
- Validation: 20% of insights manually verified quarterly

## Troubleshooting

### Common Configuration Issues
- **API rate limiting**: Implement exponential backoff
- **Data format inconsistencies**: Standardize preprocessing
- **Memory issues with large datasets**: Use streaming processing

### Performance Optimization
- Cache frequent analysis requests
- Pre-aggregate common metrics
- Use parallel processing for multiple data sources
- Implement smart sampling for very large datasets