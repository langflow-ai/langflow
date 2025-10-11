from __future__ import annotations

import asyncio
import uuid
from typing import Any

from langchain_core.tools import StructuredTool  # noqa: TC002

from langflow.api.v2.mcp import get_server
from langflow.base.agents.utils import maybe_unflatten_dict, safe_cache_get, safe_cache_set
from langflow.base.mcp.util import (
    MCPSseClient,
    MCPStdioClient,
    create_input_schema_from_json_schema,
    update_tools,
)
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs.inputs import InputTypes  # noqa: TC001
from langflow.io import DropdownInput, McpInput, MessageTextInput, Output
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.logging import logger
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message

# Import get_server from the backend API
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_settings_service, get_storage_service, session_scope


# Mock tool templates for healthcare tools when no MCP server is available
MOCK_TOOL_TEMPLATES = {
    # Healthcare EHR Tools
    "ehr_patient_records": {
        "name": "EHR Patient Records",
        "description": "Access patient electronic health records for the specific visit",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "visit_date": {"type": "string", "description": "Visit date (YYYY-MM-DD format)"},
            "record_type": {"type": "string", "description": "Type of record to retrieve", "enum": ["visit_notes", "discharge_summary", "all"]}
        },
        "mock_response": {
            "patient_id": "PAT123456",
            "visit_date": "2024-01-15",
            "visit_notes": [
                {
                    "timestamp": "2024-01-15T10:30:00Z",
                    "provider": "Dr. Smith",
                    "note_type": "Assessment",
                    "content": "Patient presents with stable chronic conditions. Medication adherence improved."
                }
            ],
            "diagnoses": ["Type 2 Diabetes Mellitus", "Hypertension", "Hyperlipidemia"],
            "medications": [
                {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily"},
                {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"}
            ],
            "vital_signs": {"bp": "130/80", "pulse": "72", "temp": "98.6F"},
            "status": "active"
        }
    },

    "pharmacy_claims_ncpdp": {
        "name": "Pharmacy Claims NCPDP",
        "description": "Access pharmacy claims data to retrieve medication fill history and refill patterns",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "date_range": {"type": "string", "description": "Date range for claims (e.g., '90d', '6m', '1y')"},
            "medication_filter": {"type": "string", "description": "Filter by specific medication or drug class"}
        },
        "mock_response": {
            "member_id": "MEM789012",
            "claims_period": "2023-10-15 to 2024-01-15",
            "prescriptions": [
                {
                    "ndc": "00093-0058-01",
                    "medication": "Metformin HCl 500mg",
                    "fill_date": "2024-01-10",
                    "days_supply": 30,
                    "quantity": 60,
                    "pharmacy": "CVS Pharmacy #1234",
                    "prescriber": "Dr. Smith"
                }
            ],
            "adherence_metrics": {
                "pdc_diabetes": 0.85,
                "pdc_hypertension": 0.72,
                "refill_gaps": ["Lisinopril: 5-day gap in December"]
            },
            "total_claims": 12
        }
    },

    "insurance_eligibility_check": {
        "name": "Insurance Eligibility Check",
        "description": "Real-time insurance eligibility verification and benefits checking",
        "input_schema": {
            "member_id": {"type": "string", "description": "Insurance member ID"},
            "provider_npi": {"type": "string", "description": "Provider NPI number"},
            "service_type": {"type": "string", "description": "Type of service", "enum": ["office_visit", "specialist", "diagnostic", "procedure"]}
        },
        "mock_response": {
            "member_id": "INS456789",
            "eligibility_status": "active",
            "coverage_effective_date": "2024-01-01",
            "plan_name": "Health Plus Premium",
            "copay_office_visit": "$25",
            "copay_specialist": "$50",
            "deductible_remaining": "$750",
            "out_of_pocket_max": "$5000",
            "prior_auth_required": False,
            "benefits": {
                "office_visits": "Covered after copay",
                "preventive_care": "100% covered",
                "prescription_drugs": "Covered with formulary"
            }
        }
    },

    "member_management_system": {
        "name": "Member Management System",
        "description": "Access member demographics and management system for patient information",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "info_type": {"type": "string", "description": "Type of information requested", "enum": ["demographics", "contact", "preferences", "all"]}
        },
        "mock_response": {
            "member_id": "MEM123456",
            "demographics": {
                "name": "John Doe",
                "date_of_birth": "1985-06-15",
                "gender": "Male",
                "address": "123 Main St, Anytown, ST 12345"
            },
            "contact_preferences": {
                "email": "john.doe@email.com",
                "phone": "555-123-4567",
                "preferred_method": "email",
                "language": "English"
            },
            "care_team": {
                "primary_care_provider": "Dr. Jane Smith",
                "care_coordinator": "Sarah Johnson, RN"
            },
            "risk_score": 65,
            "last_updated": "2024-01-15T08:00:00Z"
        }
    },

    "healthcare_nlp_sentiment": {
        "name": "Healthcare NLP Sentiment Analysis",
        "description": "Advanced NLP engine optimized for healthcare feedback sentiment analysis",
        "input_schema": {
            "text_content": {"type": "string", "description": "Text content to analyze"},
            "analysis_type": {"type": "string", "description": "Type of analysis", "enum": ["sentiment", "themes", "clinical_terms", "all"]}
        },
        "mock_response": {
            "sentiment_score": 0.75,
            "sentiment_label": "positive",
            "confidence": 0.88,
            "themes_extracted": ["staff_friendliness", "wait_time", "treatment_effectiveness"],
            "clinical_terms": ["blood_pressure", "medication", "follow_up"],
            "key_phrases": ["very satisfied", "professional staff", "timely care"],
            "processing_time_ms": 145
        }
    },

    "symptom_checker_api": {
        "name": "Symptom Checker API",
        "description": "Advanced symptom analysis and clinical triage assessment system",
        "input_schema": {
            "symptoms": {"type": "array", "description": "List of symptoms"},
            "patient_age": {"type": "integer", "description": "Patient age"},
            "patient_gender": {"type": "string", "description": "Patient gender"},
            "severity": {"type": "string", "description": "Symptom severity", "enum": ["mild", "moderate", "severe"]}
        },
        "mock_response": {
            "triage_level": "routine",
            "urgency_score": 3,
            "possible_conditions": [
                {"condition": "Upper Respiratory Infection", "probability": 0.65},
                {"condition": "Allergic Rhinitis", "probability": 0.25},
                {"condition": "Sinusitis", "probability": 0.10}
            ],
            "recommendations": [
                "Consider scheduling routine appointment with primary care",
                "Monitor symptoms for 24-48 hours",
                "Increase fluid intake and rest"
            ],
            "red_flags": [],
            "follow_up_needed": "3-5 days if symptoms persist"
        }
    },

    # HIGH PRIORITY: Patient Experience Tools
    "call_center_logs": {
        "name": "Call Center Logs Access",
        "description": "Access call center logs, transcripts, and metadata for patient feedback analysis",
        "input_schema": {
            "date_range": {"type": "string", "description": "Date range for logs (e.g., '7d', '30d', '6m')"},
            "call_type": {"type": "string", "description": "Type of call", "enum": ["appointment", "billing", "clinical", "complaint", "all"]},
            "member_id": {"type": "string", "description": "Specific member ID (optional)"},
            "sentiment_filter": {"type": "string", "description": "Filter by sentiment", "enum": ["positive", "negative", "neutral", "all"]}
        },
        "mock_response": {
            "total_calls": 1247,
            "date_range": "2024-01-01 to 2024-01-15",
            "call_summary": {
                "appointment_calls": 523,
                "billing_calls": 312,
                "clinical_calls": 298,
                "complaint_calls": 114
            },
            "sentiment_breakdown": {
                "positive": 0.42,
                "neutral": 0.35,
                "negative": 0.23
            },
            "sample_transcripts": [
                {
                    "call_id": "CALL_20240115_001",
                    "timestamp": "2024-01-15T09:30:00Z",
                    "duration_minutes": 8.5,
                    "call_type": "appointment",
                    "sentiment": "positive",
                    "summary": "Patient successfully scheduled follow-up appointment, expressed satisfaction with provider",
                    "keywords": ["appointment", "schedule", "satisfied", "follow-up"]
                },
                {
                    "call_id": "CALL_20240115_002",
                    "timestamp": "2024-01-15T11:15:00Z",
                    "duration_minutes": 12.3,
                    "call_type": "billing",
                    "sentiment": "negative",
                    "summary": "Patient concerned about unexpected charges, issue escalated to billing department",
                    "keywords": ["billing", "charges", "confused", "escalated"]
                }
            ],
            "common_issues": [
                {"issue": "Long wait times", "frequency": 0.34},
                {"issue": "Billing confusion", "frequency": 0.28},
                {"issue": "Appointment scheduling", "frequency": 0.21}
            ]
        }
    },

    "survey_responses": {
        "name": "Survey Response Access",
        "description": "Access patient survey responses across multiple survey types and platforms",
        "input_schema": {
            "survey_type": {"type": "string", "description": "Type of survey", "enum": ["satisfaction", "post_visit", "annual", "experience", "all"]},
            "date_range": {"type": "string", "description": "Date range for responses"},
            "response_status": {"type": "string", "description": "Response completion status", "enum": ["complete", "partial", "abandoned", "all"]},
            "score_range": {"type": "string", "description": "Filter by score range (e.g., '1-3', '4-5')"}
        },
        "mock_response": {
            "total_responses": 2834,
            "response_rate": 0.67,
            "survey_period": "2024-01-01 to 2024-01-15",
            "average_scores": {
                "overall_satisfaction": 4.2,
                "provider_communication": 4.5,
                "appointment_scheduling": 3.8,
                "facility_cleanliness": 4.6,
                "wait_time_satisfaction": 3.4
            },
            "response_distribution": {
                "5_stars": 0.45,
                "4_stars": 0.28,
                "3_stars": 0.15,
                "2_stars": 0.08,
                "1_star": 0.04
            },
            "recent_responses": [
                {
                    "response_id": "SURV_20240115_001",
                    "survey_type": "post_visit",
                    "overall_score": 5,
                    "completion_date": "2024-01-15T14:30:00Z",
                    "feedback_text": "Excellent care, doctor was very thorough and explained everything clearly",
                    "department": "Primary Care",
                    "provider": "Dr. Smith"
                },
                {
                    "response_id": "SURV_20240115_002",
                    "survey_type": "satisfaction",
                    "overall_score": 2,
                    "completion_date": "2024-01-15T16:45:00Z",
                    "feedback_text": "Long wait time, difficult to get appointment",
                    "department": "Cardiology",
                    "provider": "Dr. Johnson"
                }
            ],
            "trending_topics": [
                {"topic": "wait_times", "sentiment": "negative", "frequency": 0.42},
                {"topic": "staff_friendliness", "sentiment": "positive", "frequency": 0.38},
                {"topic": "appointment_availability", "sentiment": "negative", "frequency": 0.31}
            ]
        }
    },

    "complaint_management": {
        "name": "Complaint Management System",
        "description": "Access formal complaints, grievances, and resolution data from CRM systems",
        "input_schema": {
            "complaint_status": {"type": "string", "description": "Status of complaint", "enum": ["open", "investigating", "resolved", "escalated", "all"]},
            "severity_level": {"type": "string", "description": "Complaint severity", "enum": ["low", "medium", "high", "critical"]},
            "date_range": {"type": "string", "description": "Date range for complaints"},
            "department": {"type": "string", "description": "Department involved (optional)"}
        },
        "mock_response": {
            "total_complaints": 89,
            "period": "2024-01-01 to 2024-01-15",
            "status_breakdown": {
                "open": 23,
                "investigating": 31,
                "resolved": 28,
                "escalated": 7
            },
            "severity_distribution": {
                "low": 0.34,
                "medium": 0.45,
                "high": 0.18,
                "critical": 0.03
            },
            "average_resolution_time_days": 8.5,
            "departments_most_complaints": [
                {"department": "Billing", "count": 32},
                {"department": "Scheduling", "count": 21},
                {"department": "Clinical Care", "count": 18},
                {"department": "Customer Service", "count": 12}
            ],
            "recent_complaints": [
                {
                    "complaint_id": "COMP_20240115_001",
                    "submitted_date": "2024-01-15T10:00:00Z",
                    "severity": "high",
                    "status": "investigating",
                    "department": "Billing",
                    "summary": "Patient charged for services not received, insurance claim processed incorrectly",
                    "complainant_type": "patient",
                    "assigned_to": "Billing Manager"
                },
                {
                    "complaint_id": "COMP_20240115_002",
                    "submitted_date": "2024-01-15T14:30:00Z",
                    "severity": "medium",
                    "status": "open",
                    "department": "Clinical Care",
                    "summary": "Patient dissatisfied with wait time for specialist referral",
                    "complainant_type": "patient",
                    "assigned_to": "Patient Relations"
                }
            ],
            "complaint_categories": [
                {"category": "Billing/Financial", "percentage": 0.36},
                {"category": "Access/Scheduling", "percentage": 0.24},
                {"category": "Quality of Care", "percentage": 0.20},
                {"category": "Communication", "percentage": 0.20}
            ]
        }
    },

    "ehr_calendar_access": {
        "name": "EHR Calendar Access",
        "description": "Access electronic health record system for provider scheduling and availability",
        "input_schema": {
            "provider_id": {"type": "string", "description": "Provider identifier or NPI"},
            "date_range": {"type": "string", "description": "Date range for availability check"},
            "appointment_type": {"type": "string", "description": "Type of appointment", "enum": ["routine", "urgent", "follow_up", "new_patient", "procedure"]},
            "location": {"type": "string", "description": "Clinic location (optional)"}
        },
        "mock_response": {
            "provider_id": "NPI_1234567890",
            "provider_name": "Dr. Jane Smith",
            "specialty": "Internal Medicine",
            "location": "Main Clinic - Building A",
            "availability_summary": {
                "total_slots_available": 47,
                "next_available": "2024-01-17T09:00:00Z",
                "earliest_routine": "2024-01-22T14:30:00Z",
                "earliest_urgent": "2024-01-16T16:00:00Z"
            },
            "weekly_schedule": {
                "monday": {"start": "08:00", "end": "17:00", "lunch": "12:00-13:00"},
                "tuesday": {"start": "08:00", "end": "17:00", "lunch": "12:00-13:00"},
                "wednesday": {"start": "08:00", "end": "12:00", "lunch": null},
                "thursday": {"start": "08:00", "end": "17:00", "lunch": "12:00-13:00"},
                "friday": {"start": "08:00", "end": "16:00", "lunch": "12:00-13:00"}
            },
            "available_slots": [
                {
                    "date": "2024-01-17",
                    "time": "09:00",
                    "duration_minutes": 30,
                    "appointment_type": "routine",
                    "status": "available"
                },
                {
                    "date": "2024-01-17",
                    "time": "09:30",
                    "duration_minutes": 30,
                    "appointment_type": "routine",
                    "status": "available"
                },
                {
                    "date": "2024-01-17",
                    "time": "14:00",
                    "duration_minutes": 60,
                    "appointment_type": "new_patient",
                    "status": "available"
                }
            ],
            "upcoming_appointments": [
                {
                    "date": "2024-01-16",
                    "time": "10:00",
                    "patient_name": "John Doe",
                    "appointment_type": "follow_up",
                    "reason": "Diabetes management"
                }
            ]
        }
    },

    "email_service": {
        "name": "Email Communication Service",
        "description": "Email service for comprehensive patient communication and appointment management",
        "input_schema": {
            "recipient": {"type": "string", "description": "Recipient email address"},
            "message_type": {"type": "string", "description": "Type of email", "enum": ["appointment_confirmation", "reminder", "follow_up", "survey", "newsletter", "custom"]},
            "template_id": {"type": "string", "description": "Email template identifier (optional)"},
            "personalization_data": {"type": "object", "description": "Data for email personalization"}
        },
        "mock_response": {
            "email_id": "EMAIL_20240115_001",
            "status": "sent",
            "sent_timestamp": "2024-01-15T10:30:00Z",
            "recipient": "patient@example.com",
            "subject": "Appointment Confirmation - Dr. Smith on Jan 22, 2024",
            "message_type": "appointment_confirmation",
            "delivery_status": {
                "delivered": True,
                "opened": False,
                "clicked": False,
                "bounce": False,
                "complaint": False
            },
            "tracking_metrics": {
                "delivery_time_seconds": 2.3,
                "estimated_read_time": "45 seconds",
                "mobile_friendly": True,
                "accessibility_score": 0.95
            },
            "email_content": {
                "preview_text": "Your appointment with Dr. Smith is confirmed for January 22, 2024 at 2:30 PM",
                "personalization_applied": [
                    "patient_name",
                    "provider_name",
                    "appointment_date",
                    "appointment_time",
                    "location"
                ],
                "call_to_action": "Add to Calendar",
                "attachments": ["appointment_prep_instructions.pdf"]
            },
            "campaign_data": {
                "campaign_id": "APPT_CONFIRM_2024",
                "segment": "scheduled_patients",
                "a_b_test_variant": "standard"
            }
        }
    },

    "sms_gateway": {
        "name": "SMS Gateway Service",
        "description": "SMS messaging service for patient communication and notifications",
        "input_schema": {
            "phone_number": {"type": "string", "description": "Recipient phone number"},
            "message_type": {"type": "string", "description": "Type of SMS", "enum": ["appointment_reminder", "confirmation", "follow_up", "health_tip", "urgent", "survey"]},
            "message_content": {"type": "string", "description": "SMS message content"},
            "send_time": {"type": "string", "description": "Scheduled send time (optional)"}
        },
        "mock_response": {
            "message_id": "SMS_20240115_001",
            "status": "sent",
            "sent_timestamp": "2024-01-15T10:30:00Z",
            "phone_number": "+1-555-123-4567",
            "message_type": "appointment_reminder",
            "message_content": "Reminder: You have an appointment with Dr. Smith tomorrow at 2:30 PM. Reply CONFIRM to confirm or CANCEL to reschedule. Main Clinic, 123 Health St.",
            "character_count": 147,
            "segment_count": 1,
            "delivery_status": {
                "delivered": True,
                "delivery_time_seconds": 1.8,
                "carrier": "Verizon",
                "country_code": "US"
            },
            "response_tracking": {
                "response_expected": True,
                "response_received": False,
                "response_deadline": "2024-01-16T14:30:00Z",
                "auto_response_enabled": True
            },
            "cost_data": {
                "cost_per_message": 0.0075,
                "currency": "USD",
                "billing_category": "patient_communications"
            },
            "compliance": {
                "opt_in_status": "confirmed",
                "opt_in_date": "2024-01-10T09:00:00Z",
                "do_not_disturb_respected": True,
                "hipaa_compliant": True
            }
        }
    },

    # MEDIUM PRIORITY: Clinical & Analytics Tools
    "appointment_analytics": {
        "name": "Appointment Analytics Platform",
        "description": "Analytics platform for tracking appointment scheduling performance and KPIs",
        "input_schema": {
            "metric_type": {"type": "string", "description": "Type of metric", "enum": ["scheduling", "cancellation", "no_show", "satisfaction", "utilization", "all"]},
            "time_period": {"type": "string", "description": "Analysis time period", "enum": ["daily", "weekly", "monthly", "quarterly"]},
            "department": {"type": "string", "description": "Department filter (optional)"},
            "provider_id": {"type": "string", "description": "Specific provider analysis (optional)"}
        },
        "mock_response": {
            "analysis_period": "2024-01-01 to 2024-01-15",
            "total_appointments": 3247,
            "key_metrics": {
                "scheduling_efficiency": 0.87,
                "no_show_rate": 0.12,
                "cancellation_rate": 0.08,
                "average_booking_lead_time_days": 12.5,
                "same_day_availability": 0.23,
                "patient_satisfaction_score": 4.3
            },
            "department_performance": [
                {
                    "department": "Primary Care",
                    "appointments": 1523,
                    "no_show_rate": 0.10,
                    "satisfaction": 4.4,
                    "utilization": 0.92
                },
                {
                    "department": "Cardiology",
                    "appointments": 456,
                    "no_show_rate": 0.15,
                    "satisfaction": 4.2,
                    "utilization": 0.88
                },
                {
                    "department": "Orthopedics",
                    "appointments": 387,
                    "no_show_rate": 0.13,
                    "satisfaction": 4.1,
                    "utilization": 0.85
                }
            ],
            "trending_metrics": {
                "appointment_volume_trend": "increasing",
                "no_show_trend": "stable",
                "satisfaction_trend": "improving",
                "wait_time_trend": "decreasing"
            },
            "recommendations": [
                "Implement automated reminder system to reduce no-shows",
                "Expand same-day scheduling availability",
                "Focus on orthopedics department satisfaction improvement"
            ]
        }
    },

    "patient_feedback_analytics": {
        "name": "Patient Feedback Analytics",
        "description": "Advanced patient feedback and satisfaction tracking system for navigation quality improvement",
        "input_schema": {
            "feedback_source": {"type": "string", "description": "Source of feedback", "enum": ["surveys", "calls", "online", "in_person", "all"]},
            "sentiment_analysis": {"type": "boolean", "description": "Include sentiment analysis"},
            "time_period": {"type": "string", "description": "Analysis period"},
            "department_filter": {"type": "string", "description": "Filter by department (optional)"}
        },
        "mock_response": {
            "analysis_period": "2024-01-01 to 2024-01-15",
            "total_feedback_items": 1847,
            "overall_sentiment_score": 0.72,
            "sentiment_distribution": {
                "very_positive": 0.34,
                "positive": 0.28,
                "neutral": 0.23,
                "negative": 0.12,
                "very_negative": 0.03
            },
            "feedback_themes": [
                {
                    "theme": "staff_communication",
                    "sentiment": "positive",
                    "frequency": 0.45,
                    "average_score": 4.3,
                    "sample_comments": [
                        "Nurses were very helpful and explained everything",
                        "Doctor listened carefully to my concerns"
                    ]
                },
                {
                    "theme": "wait_times",
                    "sentiment": "negative",
                    "frequency": 0.38,
                    "average_score": 2.1,
                    "sample_comments": [
                        "Waited 45 minutes past appointment time",
                        "Long delays in emergency department"
                    ]
                },
                {
                    "theme": "facility_cleanliness",
                    "sentiment": "positive",
                    "frequency": 0.31,
                    "average_score": 4.6,
                    "sample_comments": [
                        "Very clean and well-maintained facilities",
                        "Impressive attention to hygiene protocols"
                    ]
                }
            ],
            "department_feedback": [
                {
                    "department": "Emergency",
                    "feedback_count": 523,
                    "average_sentiment": 0.65,
                    "primary_concerns": ["wait_times", "communication", "triage_process"]
                },
                {
                    "department": "Outpatient Surgery",
                    "feedback_count": 298,
                    "average_sentiment": 0.84,
                    "primary_concerns": ["pre_op_instructions", "post_op_care", "scheduling"]
                }
            ],
            "improvement_opportunities": [
                "Reduce wait times in primary care (target: <15 min)",
                "Enhance communication training for emergency staff",
                "Implement real-time feedback collection system"
            ],
            "trending_topics": {
                "emerging_positive": ["telehealth_experience", "appointment_flexibility"],
                "emerging_negative": ["parking_availability", "phone_system_navigation"]
            }
        }
    },

    "ehr_care_plans": {
        "name": "EHR Care Plans Access",
        "description": "Access electronic health record care plans and clinical protocols",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "care_plan_type": {"type": "string", "description": "Type of care plan", "enum": ["chronic_disease", "post_acute", "preventive", "wellness", "all"]},
            "active_only": {"type": "boolean", "description": "Return only active care plans"},
            "include_goals": {"type": "boolean", "description": "Include care plan goals and outcomes"}
        },
        "mock_response": {
            "patient_id": "PAT123456",
            "total_care_plans": 3,
            "active_care_plans": 2,
            "last_updated": "2024-01-15T08:00:00Z",
            "care_plans": [
                {
                    "care_plan_id": "CP_DIABETES_001",
                    "plan_type": "chronic_disease",
                    "condition": "Type 2 Diabetes Mellitus",
                    "status": "active",
                    "start_date": "2023-06-15",
                    "next_review_date": "2024-03-15",
                    "care_team": [
                        {"role": "Primary Care Provider", "name": "Dr. Jane Smith"},
                        {"role": "Diabetes Educator", "name": "Sarah Johnson, RN"},
                        {"role": "Nutritionist", "name": "Mike Chen, RD"}
                    ],
                    "goals": [
                        {
                            "goal": "HbA1c < 7%",
                            "target_date": "2024-06-15",
                            "current_value": "7.2%",
                            "status": "in_progress"
                        },
                        {
                            "goal": "Weight loss 10 lbs",
                            "target_date": "2024-04-15",
                            "current_value": "-6 lbs",
                            "status": "on_track"
                        }
                    ],
                    "interventions": [
                        "Metformin 500mg twice daily",
                        "Blood glucose monitoring 2x daily",
                        "Nutritionist consultation monthly",
                        "Exercise plan: 30 min walking 5x/week"
                    ],
                    "next_actions": [
                        "Lab work scheduled for 2024-01-22",
                        "Follow-up appointment with Dr. Smith on 2024-01-29"
                    ]
                },
                {
                    "care_plan_id": "CP_HYPERTENSION_001",
                    "plan_type": "chronic_disease",
                    "condition": "Hypertension",
                    "status": "active",
                    "start_date": "2023-08-20",
                    "next_review_date": "2024-02-20",
                    "care_team": [
                        {"role": "Primary Care Provider", "name": "Dr. Jane Smith"},
                        {"role": "Pharmacist", "name": "David Lee, PharmD"}
                    ],
                    "goals": [
                        {
                            "goal": "Blood pressure < 130/80",
                            "target_date": "2024-05-20",
                            "current_value": "138/85",
                            "status": "needs_adjustment"
                        }
                    ],
                    "interventions": [
                        "Lisinopril 10mg once daily",
                        "Home blood pressure monitoring",
                        "DASH diet consultation",
                        "Sodium restriction < 2g daily"
                    ]
                }
            ],
            "quality_measures": {
                "diabetes_control": "needs_improvement",
                "hypertension_control": "adequate",
                "medication_adherence_score": 0.78,
                "care_plan_completion_rate": 0.85
            }
        }
    },

    "medication_records": {
        "name": "Medication Records Access",
        "description": "Access detailed medication information for patient questions and medication management",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "medication_name": {"type": "string", "description": "Specific medication name (optional)"},
            "active_only": {"type": "boolean", "description": "Return only active medications"},
            "include_history": {"type": "boolean", "description": "Include medication history and changes"}
        },
        "mock_response": {
            "patient_id": "PAT123456",
            "total_medications": 8,
            "active_medications": 5,
            "last_updated": "2024-01-15T10:00:00Z",
            "current_medications": [
                {
                    "medication_id": "MED_001",
                    "name": "Metformin",
                    "generic_name": "Metformin Hydrochloride",
                    "strength": "500mg",
                    "dosage_form": "tablet",
                    "directions": "Take 1 tablet by mouth twice daily with meals",
                    "quantity": 60,
                    "days_supply": 30,
                    "refills_remaining": 3,
                    "prescriber": "Dr. Jane Smith",
                    "pharmacy": "CVS Pharmacy #1234",
                    "date_prescribed": "2023-12-15",
                    "last_filled": "2024-01-10",
                    "next_refill_due": "2024-02-09",
                    "indication": "Type 2 Diabetes Mellitus",
                    "status": "active"
                },
                {
                    "medication_id": "MED_002",
                    "name": "Lisinopril",
                    "generic_name": "Lisinopril",
                    "strength": "10mg",
                    "dosage_form": "tablet",
                    "directions": "Take 1 tablet by mouth once daily",
                    "quantity": 30,
                    "days_supply": 30,
                    "refills_remaining": 5,
                    "prescriber": "Dr. Jane Smith",
                    "pharmacy": "CVS Pharmacy #1234",
                    "date_prescribed": "2023-11-20",
                    "last_filled": "2024-01-05",
                    "next_refill_due": "2024-02-04",
                    "indication": "Hypertension",
                    "status": "active"
                }
            ],
            "medication_alerts": [
                {
                    "alert_type": "refill_reminder",
                    "medication": "Metformin",
                    "message": "Refill due in 5 days",
                    "priority": "medium"
                },
                {
                    "alert_type": "interaction_check",
                    "medications": ["Metformin", "Lisinopril"],
                    "message": "No significant interactions detected",
                    "priority": "low"
                }
            ],
            "adherence_data": {
                "overall_adherence_score": 0.85,
                "medications_on_schedule": 4,
                "medications_delayed": 1,
                "missed_doses_last_30_days": 3,
                "adherence_trend": "improving"
            },
            "medication_history": [
                {
                    "action": "prescribed",
                    "medication": "Metformin 500mg",
                    "date": "2023-12-15",
                    "provider": "Dr. Jane Smith",
                    "reason": "Initial diabetes management"
                },
                {
                    "action": "dosage_increased",
                    "medication": "Lisinopril 5mg to 10mg",
                    "date": "2024-01-02",
                    "provider": "Dr. Jane Smith",
                    "reason": "Blood pressure not at target"
                }
            ]
        }
    }
}


class MCPToolsComponent(ComponentWithCache):
    schema_inputs: list = []
    tools: list[StructuredTool] = []
    _not_load_actions: bool = False
    _tool_cache: dict = {}
    _last_selected_server: str | None = None  # Cache for the last selected server

    # Mock mode capabilities
    mock_mode: bool = False
    mock_tools: list[StructuredTool] = []
    _mock_tool_cache: dict = {}

    def __init__(self, **data) -> None:
        super().__init__(**data)
        # Initialize cache keys to avoid CacheMiss when accessing them
        self._ensure_cache_structure()

        # Initialize clients with access to the component cache
        self.stdio_client: MCPStdioClient = MCPStdioClient(component_cache=self._shared_component_cache)
        self.sse_client: MCPSseClient = MCPSseClient(component_cache=self._shared_component_cache)

        # Initialize mock mode
        self.mock_mode = False
        self.mock_tools = []
        self._mock_tool_cache = {}

    def _ensure_cache_structure(self):
        """Ensure the cache has the required structure."""
        # Check if servers key exists and is not CacheMiss
        servers_value = safe_cache_get(self._shared_component_cache, "servers")
        if servers_value is None:
            safe_cache_set(self._shared_component_cache, "servers", {})

        # Check if last_selected_server key exists and is not CacheMiss
        last_server_value = safe_cache_get(self._shared_component_cache, "last_selected_server")
        if last_server_value is None:
            safe_cache_set(self._shared_component_cache, "last_selected_server", "")

    default_keys: list[str] = [
        "code",
        "_type",
        "tool_mode",
        "tool_placeholder",
        "mcp_server",
        "tool",
    ]

    display_name = "MCP Tools"
    description = "Connect to an MCP server to use its tools."
    documentation: str = "https://docs.langflow.org/mcp-client"
    icon = "Mcp"
    name = "MCPTools"

    inputs = [
        McpInput(
            name="mcp_server",
            display_name="MCP Server",
            info="Select the MCP Server that will be used by this component",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="tool",
            display_name="Tool",
            options=[],
            value="",
            info="Select the tool to execute",
            show=False,
            required=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="tool_placeholder",
            display_name="Tool Placeholder",
            info="Placeholder for the tool",
            value="",
            show=False,
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="build_output"),
    ]

    async def _validate_schema_inputs(self, tool_obj) -> list[InputTypes]:
        """Validate and process schema inputs for a tool."""
        try:
            if not tool_obj or not hasattr(tool_obj, "args_schema"):
                msg = "Invalid tool object or missing input schema"
                raise ValueError(msg)

            flat_schema = flatten_schema(tool_obj.args_schema.schema())
            input_schema = create_input_schema_from_json_schema(flat_schema)
            if not input_schema:
                msg = f"Empty input schema for tool '{tool_obj.name}'"
                raise ValueError(msg)

            schema_inputs = schema_to_langflow_inputs(input_schema)
            if not schema_inputs:
                msg = f"No input parameters defined for tool '{tool_obj.name}'"
                await logger.awarning(msg)
                return []

        except Exception as e:
            msg = f"Error validating schema inputs: {e!s}"
            await logger.aexception(msg)
            raise ValueError(msg) from e
        else:
            return schema_inputs

    def _has_valid_server_connection(self, server_config=None) -> bool:
        """Check if we have a valid MCP server connection available."""
        if not server_config:
            return False

        # Check if we have connection details (command for STDIO or url for SSE)
        has_command = server_config.get("command") and server_config["command"].strip()
        has_url = server_config.get("url") and server_config["url"].strip()

        # If we only have the default placeholder command, it's not a real server
        if has_command and "echo" in server_config["command"] and "tools" in server_config["command"]:
            return False

        return has_command or has_url

    def _generate_mock_tool_from_config(self, tool_name: str, description: str = "") -> StructuredTool:
        """Generate a mock tool based on tool_name and description from Genesis config."""
        from pydantic import BaseModel, Field

        # Get template if available, otherwise create generic
        template = MOCK_TOOL_TEMPLATES.get(tool_name, {
            "name": tool_name.replace("_", " ").title(),
            "description": description or f"Mock tool for {tool_name}",
            "input_schema": {
                "input_data": {"type": "string", "description": "Input data for the tool"}
            },
            "mock_response": {
                "tool_name": tool_name,
                "status": "success",
                "data": "Mock response data",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        })

        # Create Pydantic model for input schema
        schema_fields = {}
        for field_name, field_info in template["input_schema"].items():
            field_type = str  # Default to string
            if field_info["type"] == "integer":
                field_type = int
            elif field_info["type"] == "array":
                field_type = list

            schema_fields[field_name] = (field_type, Field(description=field_info["description"]))

        InputSchema = type(f"{tool_name}_Schema", (BaseModel,), schema_fields)

        # Create mock function
        def mock_function(**kwargs) -> dict:
            """Mock function that returns predefined response."""
            response = template["mock_response"].copy()
            # Include input parameters in response for traceability
            response["input_parameters"] = kwargs
            response["mock_mode"] = True
            return response

        # Create StructuredTool
        return StructuredTool(
            name=tool_name,
            description=template["description"],
            func=mock_function,
            args_schema=InputSchema
        )

    async def _generate_mock_tools_from_component_config(self) -> list[StructuredTool]:
        """Generate mock tools based on component configuration."""
        tools = []

        # Check if we have tool_name in our configuration
        # This comes from Genesis specification config merged with mapper defaults
        config = getattr(self, '_component_config', {})

        tool_name = config.get('tool_name')
        description = config.get('description', '')

        if tool_name:
            await logger.ainfo(f"Generating mock tool for: {tool_name}")
            mock_tool = self._generate_mock_tool_from_config(tool_name, description)
            tools.append(mock_tool)

            # Cache the mock tool
            self._mock_tool_cache[tool_name] = mock_tool
        else:
            await logger.awarning("No tool_name found in component config for mock generation")

        return tools

    async def _try_mock_mode_fallback(self, server_name: str, server_config: dict = None) -> tuple[list, dict]:
        """Fallback to mock mode when no real server is available."""
        await logger.ainfo(f"Falling back to mock mode for server: {server_name}")

        self.mock_mode = True

        # Generate mock tools based on component configuration
        mock_tools = self._generate_mock_tools_from_component_config()

        if mock_tools:
            self.tools = mock_tools
            self.tool_names = [tool.name for tool in mock_tools]
            self._tool_cache = {tool.name: tool for tool in mock_tools}

            # Create mock server config for caching
            mock_server_config = {
                "mock_mode": True,
                "tool_name": getattr(self, '_component_config', {}).get('tool_name', 'unknown'),
                "description": getattr(self, '_component_config', {}).get('description', '')
            }

            await logger.ainfo(f"Generated {len(mock_tools)} mock tools: {self.tool_names}")
            return mock_tools, {"name": server_name, "config": mock_server_config}
        else:
            await logger.awarning("No mock tools could be generated")
            return [], {"name": server_name, "config": server_config}

    async def update_tool_list(self, mcp_server_value=None):
        # Accepts mcp_server_value as dict {name, config} or uses self.mcp_server
        mcp_server = mcp_server_value if mcp_server_value is not None else getattr(self, "mcp_server", None)
        server_name = None
        server_config_from_value = None
        if isinstance(mcp_server, dict):
            server_name = mcp_server.get("name")
            server_config_from_value = mcp_server.get("config")
        else:
            server_name = mcp_server
        if not server_name:
            self.tools = []
            return [], {"name": server_name, "config": server_config_from_value}

        # Use shared cache if available
        servers_cache = safe_cache_get(self._shared_component_cache, "servers", {})
        cached = servers_cache.get(server_name) if isinstance(servers_cache, dict) else None

        if cached is not None:
            self.tools = cached["tools"]
            self.tool_names = cached["tool_names"]
            self._tool_cache = cached["tool_cache"]
            server_config_from_value = cached["config"]
            return self.tools, {"name": server_name, "config": server_config_from_value}

        try:
            async with session_scope() as db:
                if not self.user_id:
                    msg = "User ID is required for fetching MCP tools."
                    raise ValueError(msg)
                current_user = await get_user_by_id(db, self.user_id)

                # Try to get server config from DB/API
                server_config = await get_server(
                    server_name,
                    current_user,
                    db,
                    storage_service=get_storage_service(),
                    settings_service=get_settings_service(),
                )

            # If get_server returns empty but we have a config, use it
            if not server_config and server_config_from_value:
                server_config = server_config_from_value

            # Check if we have a valid server connection or should fall back to mock mode
            if not server_config or not self._has_valid_server_connection(server_config):
                await logger.ainfo(f"No valid server connection found for {server_name}, attempting mock mode fallback")

                # Store component config for mock tool generation
                if server_config_from_value:
                    self._component_config = server_config_from_value
                elif hasattr(self, 'template') and self.template:
                    # Extract config from component template if available
                    template_config = {}
                    for key, value in self.template.items():
                        if isinstance(value, dict) and 'value' in value:
                            template_config[key] = value['value']
                    self._component_config = template_config
                else:
                    self._component_config = {}

                return await self._try_mock_mode_fallback(server_name, server_config)

            # Try real MCP server connection
            _, tool_list, tool_cache = await update_tools(
                server_name=server_name,
                server_config=server_config,
                mcp_stdio_client=self.stdio_client,
                mcp_sse_client=self.sse_client,
            )

            self.tool_names = [tool.name for tool in tool_list if hasattr(tool, "name")]
            self._tool_cache = tool_cache
            self.tools = tool_list
            # Cache the result using shared cache
            cache_data = {
                "tools": tool_list,
                "tool_names": self.tool_names,
                "tool_cache": tool_cache,
                "config": server_config,
            }

            # Safely update the servers cache
            current_servers_cache = safe_cache_get(self._shared_component_cache, "servers", {})
            if isinstance(current_servers_cache, dict):
                current_servers_cache[server_name] = cache_data
                safe_cache_set(self._shared_component_cache, "servers", current_servers_cache)

        except (TimeoutError, asyncio.TimeoutError) as e:
            msg = f"Timeout updating tool list: {e!s}"
            await logger.aexception(msg)
            # Try mock mode as fallback for timeout
            await logger.ainfo("Attempting mock mode fallback due to timeout")
            return await self._try_mock_mode_fallback(server_name, server_config)
        except Exception as e:
            msg = f"Error updating tool list: {e!s}"
            await logger.aexception(msg)
            # Try mock mode as fallback for any other error
            await logger.ainfo("Attempting mock mode fallback due to error")
            return await self._try_mock_mode_fallback(server_name, server_config)
        else:
            return tool_list, {"name": server_name, "config": server_config}

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Toggle the visibility of connection-specific fields based on the selected mode."""
        try:
            if field_name == "tool":
                try:
                    if len(self.tools) == 0:
                        try:
                            self.tools, build_config["mcp_server"]["value"] = await self.update_tool_list()
                            build_config["tool"]["options"] = [tool.name for tool in self.tools]
                            build_config["tool"]["placeholder"] = "Select a tool"
                        except (TimeoutError, asyncio.TimeoutError) as e:
                            msg = f"Timeout updating tool list: {e!s}"
                            await logger.aexception(msg)
                            if not build_config["tools_metadata"]["show"]:
                                build_config["tool"]["show"] = True
                                build_config["tool"]["options"] = []
                                build_config["tool"]["value"] = ""
                                build_config["tool"]["placeholder"] = "Timeout on MCP server"
                            else:
                                build_config["tool"]["show"] = False
                        except ValueError:
                            if not build_config["tools_metadata"]["show"]:
                                build_config["tool"]["show"] = True
                                build_config["tool"]["options"] = []
                                build_config["tool"]["value"] = ""
                                build_config["tool"]["placeholder"] = "Error on MCP Server"
                            else:
                                build_config["tool"]["show"] = False

                    if field_value == "":
                        return build_config
                    tool_obj = None
                    for tool in self.tools:
                        if tool.name == field_value:
                            tool_obj = tool
                            break
                    if tool_obj is None:
                        msg = f"Tool {field_value} not found in available tools: {self.tools}"
                        await logger.awarning(msg)
                        return build_config
                    await self._update_tool_config(build_config, field_value)
                except Exception as e:
                    build_config["tool"]["options"] = []
                    msg = f"Failed to update tools: {e!s}"
                    raise ValueError(msg) from e
                else:
                    return build_config
            elif field_name == "mcp_server":
                if not field_value:
                    build_config["tool"]["show"] = False
                    build_config["tool"]["options"] = []
                    build_config["tool"]["value"] = ""
                    build_config["tool"]["placeholder"] = ""
                    build_config["tool_placeholder"]["tool_mode"] = False
                    self.remove_non_default_keys(build_config)
                    return build_config

                build_config["tool_placeholder"]["tool_mode"] = True

                current_server_name = field_value.get("name") if isinstance(field_value, dict) else field_value
                _last_selected_server = safe_cache_get(self._shared_component_cache, "last_selected_server", "")

                # To avoid unnecessary updates, only proceed if the server has actually changed
                if (_last_selected_server in (current_server_name, "")) and build_config["tool"]["show"]:
                    if current_server_name:
                        servers_cache = safe_cache_get(self._shared_component_cache, "servers", {})
                        if isinstance(servers_cache, dict):
                            cached = servers_cache.get(current_server_name)
                            if cached is not None and cached.get("tool_names"):
                                cached_tools = cached["tool_names"]
                                current_tools = build_config["tool"]["options"]
                                if current_tools == cached_tools:
                                    return build_config
                    else:
                        return build_config

                # Determine if "Tool Mode" is active by checking if the tool dropdown is hidden.
                is_in_tool_mode = build_config["tools_metadata"]["show"]
                safe_cache_set(self._shared_component_cache, "last_selected_server", current_server_name)

                # Check if tools are already cached for this server before clearing
                cached_tools = None
                if current_server_name:
                    servers_cache = safe_cache_get(self._shared_component_cache, "servers", {})
                    if isinstance(servers_cache, dict):
                        cached = servers_cache.get(current_server_name)
                        if cached is not None:
                            cached_tools = cached["tools"]
                            self.tools = cached_tools
                            self.tool_names = cached["tool_names"]
                            self._tool_cache = cached["tool_cache"]

                # Only clear tools if we don't have cached tools for the current server
                if not cached_tools:
                    self.tools = []  # Clear previous tools only if no cache

                self.remove_non_default_keys(build_config)  # Clear previous tool inputs

                # Only show the tool dropdown if not in tool_mode
                if not is_in_tool_mode:
                    build_config["tool"]["show"] = True
                    if cached_tools:
                        # Use cached tools to populate options immediately
                        build_config["tool"]["options"] = [tool.name for tool in cached_tools]
                        build_config["tool"]["placeholder"] = "Select a tool"
                    else:
                        # Show loading state only when we need to fetch tools
                        build_config["tool"]["placeholder"] = "Loading tools..."
                        build_config["tool"]["options"] = []
                    build_config["tool"]["value"] = uuid.uuid4()
                else:
                    # Keep the tool dropdown hidden if in tool_mode
                    self._not_load_actions = True
                    build_config["tool"]["show"] = False

            elif field_name == "tool_mode":
                build_config["tool"]["placeholder"] = ""
                build_config["tool"]["show"] = not bool(field_value) and bool(build_config["mcp_server"])
                self.remove_non_default_keys(build_config)
                self.tool = build_config["tool"]["value"]
                if field_value:
                    self._not_load_actions = True
                else:
                    build_config["tool"]["value"] = uuid.uuid4()
                    build_config["tool"]["options"] = []
                    build_config["tool"]["show"] = True
                    build_config["tool"]["placeholder"] = "Loading tools..."
            elif field_name == "tools_metadata":
                self._not_load_actions = False

        except Exception as e:
            msg = f"Error in update_build_config: {e!s}"
            await logger.aexception(msg)
            raise ValueError(msg) from e
        else:
            return build_config

    def get_inputs_for_all_tools(self, tools: list) -> dict:
        """Get input schemas for all tools."""
        inputs = {}
        for tool in tools:
            if not tool or not hasattr(tool, "name"):
                continue
            try:
                flat_schema = flatten_schema(tool.args_schema.schema())
                input_schema = create_input_schema_from_json_schema(flat_schema)
                langflow_inputs = schema_to_langflow_inputs(input_schema)
                inputs[tool.name] = langflow_inputs
            except (AttributeError, ValueError, TypeError, KeyError) as e:
                msg = f"Error getting inputs for tool {getattr(tool, 'name', 'unknown')}: {e!s}"
                logger.exception(msg)
                continue
        return inputs

    def remove_input_schema_from_build_config(
        self, build_config: dict, tool_name: str, input_schema: dict[list[InputTypes], Any]
    ):
        """Remove the input schema for the tool from the build config."""
        # Keep only schemas that don't belong to the current tool
        input_schema = {k: v for k, v in input_schema.items() if k != tool_name}
        # Remove all inputs from other tools
        for value in input_schema.values():
            for _input in value:
                if _input.name in build_config:
                    build_config.pop(_input.name)

    def remove_non_default_keys(self, build_config: dict) -> None:
        """Remove non-default keys from the build config."""
        for key in list(build_config.keys()):
            if key not in self.default_keys:
                build_config.pop(key)

    async def _update_tool_config(self, build_config: dict, tool_name: str) -> None:
        """Update tool configuration with proper error handling."""
        if not self.tools:
            self.tools, build_config["mcp_server"]["value"] = await self.update_tool_list()

        if not tool_name:
            return

        tool_obj = next((tool for tool in self.tools if tool.name == tool_name), None)
        if not tool_obj:
            msg = f"Tool {tool_name} not found in available tools: {self.tools}"
            self.remove_non_default_keys(build_config)
            build_config["tool"]["value"] = ""
            await logger.awarning(msg)
            return

        try:
            # Store current values before removing inputs
            current_values = {}
            for key, value in build_config.items():
                if key not in self.default_keys and isinstance(value, dict) and "value" in value:
                    current_values[key] = value["value"]

            # Get all tool inputs and remove old ones
            input_schema_for_all_tools = self.get_inputs_for_all_tools(self.tools)
            self.remove_input_schema_from_build_config(build_config, tool_name, input_schema_for_all_tools)

            # Get and validate new inputs
            self.schema_inputs = await self._validate_schema_inputs(tool_obj)
            if not self.schema_inputs:
                msg = f"No input parameters to configure for tool '{tool_name}'"
                await logger.ainfo(msg)
                return

            # Add new inputs to build config
            for schema_input in self.schema_inputs:
                if not schema_input or not hasattr(schema_input, "name"):
                    msg = "Invalid schema input detected, skipping"
                    await logger.awarning(msg)
                    continue

                try:
                    name = schema_input.name
                    input_dict = schema_input.to_dict()
                    input_dict.setdefault("value", None)
                    input_dict.setdefault("required", True)

                    build_config[name] = input_dict

                    # Preserve existing value if the parameter name exists in current_values
                    if name in current_values:
                        build_config[name]["value"] = current_values[name]

                except (AttributeError, KeyError, TypeError) as e:
                    msg = f"Error processing schema input {schema_input}: {e!s}"
                    await logger.aexception(msg)
                    continue
        except ValueError as e:
            msg = f"Schema validation error for tool {tool_name}: {e!s}"
            await logger.aexception(msg)
            self.schema_inputs = []
            return
        except (AttributeError, KeyError, TypeError) as e:
            msg = f"Error updating tool config: {e!s}"
            await logger.aexception(msg)
            raise ValueError(msg) from e

    async def build_output(self) -> DataFrame:
        """Build output with improved error handling and validation."""
        try:
            self.tools, _ = await self.update_tool_list()
            if self.tool != "":
                # Set session context for persistent MCP sessions using Langflow session ID
                session_context = self._get_session_context()
                if session_context:
                    self.stdio_client.set_session_context(session_context)
                    self.sse_client.set_session_context(session_context)

                exec_tool = self._tool_cache[self.tool]
                tool_args = self.get_inputs_for_all_tools(self.tools)[self.tool]
                kwargs = {}
                for arg in tool_args:
                    value = getattr(self, arg.name, None)
                    if value is not None:
                        if isinstance(value, Message):
                            kwargs[arg.name] = value.text
                        else:
                            kwargs[arg.name] = value

                unflattened_kwargs = maybe_unflatten_dict(kwargs)

                output = await exec_tool.coroutine(**unflattened_kwargs)

                tool_content = []
                for item in output.content:
                    item_dict = item.model_dump()
                    tool_content.append(item_dict)
                return DataFrame(data=tool_content)
            return DataFrame(data=[{"error": "You must select a tool"}])
        except Exception as e:
            msg = f"Error in build_output: {e!s}"
            await logger.aexception(msg)
            raise ValueError(msg) from e

    def _get_session_context(self) -> str | None:
        """Get the Langflow session ID for MCP session caching."""
        # Try to get session ID from the component's execution context
        if hasattr(self, "graph") and hasattr(self.graph, "session_id"):
            session_id = self.graph.session_id
            # Include server name to ensure different servers get different sessions
            server_name = ""
            mcp_server = getattr(self, "mcp_server", None)
            if isinstance(mcp_server, dict):
                server_name = mcp_server.get("name", "")
            elif mcp_server:
                server_name = str(mcp_server)
            return f"{session_id}_{server_name}" if session_id else None
        return None

    async def _get_tools(self):
        """Get cached tools or update if necessary."""
        mcp_server = getattr(self, "mcp_server", None)
        if not self._not_load_actions:
            tools, _ = await self.update_tool_list(mcp_server)
            return tools
        return []
