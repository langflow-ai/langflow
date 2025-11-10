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
                "wednesday": {"start": "08:00", "end": "12:00", "lunch": None},
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
    },

    # HIGH PRIORITY: Core Healthcare Operations Tools
    "api_component": {
        "name": "Generic API Integration Component",
        "description": "Flexible API integration tool for connecting with various healthcare systems and external services",
        "input_schema": {
            "endpoint": {"type": "string", "description": "API endpoint URL"},
            "method": {"type": "string", "description": "HTTP method", "enum": ["GET", "POST", "PUT", "DELETE"]},
            "payload": {"type": "object", "description": "Request payload data"},
            "headers": {"type": "object", "description": "Custom headers for the request"}
        },
        "mock_response": {
            "request_id": "API_REQ_20240115_001",
            "status": "success",
            "response_time_ms": 234,
            "data": {
                "operation": "healthcare_data_sync",
                "records_processed": 1247,
                "timestamp": "2024-01-15T10:30:00Z",
                "sync_status": "completed"
            },
            "metadata": {
                "api_version": "v2.1",
                "rate_limit_remaining": 4756,
                "next_allowed_request": "2024-01-15T10:30:01Z"
            },
            "validation": {
                "schema_valid": True,
                "data_integrity_check": "passed",
                "security_scan": "clean"
            }
        }
    },

    "encoder_pro": {
        "name": "Medical Coding and Validation Tool",
        "description": "Advanced medical coding engine for ICD-10, CPT, and HCPCS code validation and suggestions",
        "input_schema": {
            "service_code": {"type": "string", "description": "Medical service or procedure code"},
            "diagnosis_codes": {"type": "array", "description": "List of diagnosis codes"},
            "validation_type": {"type": "string", "description": "Type of validation", "enum": ["code_validity", "medical_necessity", "coverage", "all"]},
            "payer_type": {"type": "string", "description": "Insurance payer type", "enum": ["medicare", "medicaid", "commercial", "all"]}
        },
        "mock_response": {
            "validation_id": "VAL_20240115_001",
            "service_code": "99213",
            "code_description": "Office/outpatient visit, established patient, low complexity",
            "validation_status": "valid",
            "medical_necessity": {
                "supported": True,
                "confidence_score": 0.92,
                "supporting_diagnoses": ["E11.9", "I10"],
                "evidence_level": "strong"
            },
            "coverage_analysis": {
                "medicare_covered": True,
                "medicaid_covered": True,
                "commercial_covered": True,
                "prior_auth_required": False
            },
            "coding_suggestions": [
                {
                    "alternative_code": "99214",
                    "description": "Office visit, moderate complexity",
                    "reason": "Better documentation support for complexity level",
                    "reimbursement_impact": "+15%"
                }
            ],
            "compliance_flags": [],
            "processing_time_ms": 156
        }
    },

    "pa_lookup": {
        "name": "Prior Authorization Lookup Tool",
        "description": "Comprehensive prior authorization requirements lookup and status checking system",
        "input_schema": {
            "service_code": {"type": "string", "description": "CPT or HCPCS service code"},
            "diagnosis_code": {"type": "string", "description": "Primary diagnosis code"},
            "member_id": {"type": "string", "description": "Member identifier"},
            "payer_id": {"type": "string", "description": "Insurance payer identifier"},
            "provider_npi": {"type": "string", "description": "Provider NPI number"}
        },
        "mock_response": {
            "lookup_id": "PA_LOOKUP_20240115_001",
            "service_code": "77058",
            "service_description": "Mammography, bilateral",
            "pa_requirement": {
                "required": True,
                "urgency_level": "routine",
                "estimated_approval_time_days": 3,
                "submission_method": "electronic"
            },
            "payer_specific_rules": {
                "payer_name": "Blue Cross Blue Shield",
                "plan_type": "PPO",
                "medical_necessity_criteria": [
                    "Age 40+ for routine screening",
                    "Family history documentation if under 40",
                    "Previous imaging results if follow-up"
                ],
                "required_documentation": [
                    "Clinical notes supporting indication",
                    "Previous mammography reports (if applicable)",
                    "Family history questionnaire"
                ]
            },
            "existing_authorizations": [
                {
                    "auth_number": "AUTH123456789",
                    "status": "approved",
                    "valid_from": "2024-01-01",
                    "valid_to": "2024-12-31",
                    "services_covered": 1,
                    "services_used": 0
                }
            ],
            "recommendation": "Prior authorization required - existing annual auth available",
            "next_steps": ["Verify member eligibility", "Submit PA request with clinical documentation"]
        }
    },

    "eligibility_check": {
        "name": "Member Eligibility Validation Tool",
        "description": "Real-time insurance eligibility verification and benefits checking system",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "service_date": {"type": "string", "description": "Date of service (YYYY-MM-DD)"},
            "service_codes": {"type": "array", "description": "List of service codes to check"},
            "provider_npi": {"type": "string", "description": "Rendering provider NPI"}
        },
        "mock_response": {
            "eligibility_id": "ELIG_20240115_001",
            "member_id": "MEM789012345",
            "eligibility_status": "active",
            "effective_date": "2024-01-01",
            "termination_date": "2024-12-31",
            "plan_details": {
                "plan_name": "Health Plus PPO",
                "group_number": "GRP001234",
                "plan_type": "PPO",
                "network_status": "in_network"
            },
            "benefits_summary": {
                "deductible": {
                    "individual_annual": 1500,
                    "individual_remaining": 1200,
                    "family_annual": 3000,
                    "family_remaining": 2400
                },
                "out_of_pocket_max": {
                    "individual_annual": 6000,
                    "individual_remaining": 5100,
                    "family_annual": 12000,
                    "family_remaining": 10200
                },
                "copayments": {
                    "primary_care": 25,
                    "specialist": 50,
                    "emergency_room": 200,
                    "urgent_care": 75
                }
            },
            "service_coverage": [
                {
                    "service_code": "99213",
                    "covered": True,
                    "copay": 25,
                    "coinsurance": 0,
                    "prior_auth_required": False
                }
            ],
            "verification_source": "real_time_270_271",
            "last_updated": "2024-01-15T10:30:00Z"
        }
    },

    "ehr_systems_integration": {
        "name": "Multi-EHR Systems Integration",
        "description": "Comprehensive EHR integration platform for accessing patient data across multiple healthcare systems",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "ehr_systems": {"type": "array", "description": "List of EHR systems to query"},
            "data_types": {"type": "array", "description": "Types of data to retrieve", "enum": ["demographics", "medications", "allergies", "lab_results", "visits", "all"]},
            "date_range": {"type": "string", "description": "Date range for clinical data"}
        },
        "mock_response": {
            "integration_id": "EHR_INT_20240115_001",
            "patient_id": "PAT789012",
            "systems_queried": ["Epic", "Cerner", "Allscripts"],
            "data_consolidated": {
                "demographics": {
                    "name": "John Smith",
                    "dob": "1975-08-15",
                    "gender": "Male",
                    "mrn_mappings": {
                        "Epic": "EPI123456",
                        "Cerner": "CER789012",
                        "Allscripts": "ALL345678"
                    }
                },
                "medications": [
                    {
                        "medication": "Lisinopril 10mg",
                        "source_system": "Epic",
                        "prescriber": "Dr. Johnson",
                        "start_date": "2023-06-15",
                        "status": "active"
                    },
                    {
                        "medication": "Metformin 500mg",
                        "source_system": "Cerner",
                        "prescriber": "Dr. Smith",
                        "start_date": "2023-08-01",
                        "status": "active"
                    }
                ],
                "allergies": [
                    {
                        "allergen": "Penicillin",
                        "reaction": "Rash",
                        "severity": "Moderate",
                        "source_system": "Epic"
                    }
                ],
                "recent_visits": [
                    {
                        "date": "2024-01-10",
                        "provider": "Dr. Johnson",
                        "facility": "Metro Medical Center",
                        "diagnosis": "Hypertension follow-up",
                        "source_system": "Epic"
                    }
                ]
            },
            "data_quality": {
                "completeness_score": 0.89,
                "consistency_score": 0.94,
                "duplicate_records_found": 2,
                "conflicts_resolved": 1
            },
            "integration_metadata": {
                "systems_available": 3,
                "systems_responded": 3,
                "response_time_seconds": 2.8,
                "last_sync": "2024-01-15T10:30:00Z"
            }
        }
    },

    "referral_management_systems": {
        "name": "Referral Management Platform Integration",
        "description": "Comprehensive referral coordination platform for managing specialist referrals and care transitions",
        "input_schema": {
            "referral_id": {"type": "string", "description": "Referral identifier (optional for new referrals)"},
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "specialty_type": {"type": "string", "description": "Specialty type for referral"},
            "urgency_level": {"type": "string", "description": "Referral urgency", "enum": ["routine", "urgent", "stat"]},
            "operation": {"type": "string", "description": "Operation type", "enum": ["create", "status_check", "update", "search"]}
        },
        "mock_response": {
            "referral_id": "REF_20240115_001",
            "patient_id": "PAT789012",
            "referral_status": "pending_appointment",
            "specialty_requested": "Cardiology",
            "referring_provider": {
                "name": "Dr. Jane Smith",
                "npi": "1234567890",
                "facility": "Primary Care Associates"
            },
            "target_provider": {
                "name": "Dr. Michael Chen",
                "npi": "0987654321",
                "facility": "Heart & Vascular Center",
                "next_available": "2024-01-22T14:00:00Z"
            },
            "referral_details": {
                "reason": "Abnormal EKG findings",
                "clinical_summary": "Patient presents with irregular rhythm on routine EKG",
                "urgency": "routine",
                "requested_services": ["Consultation", "Echocardiogram"],
                "insurance_verified": True
            },
            "workflow_status": {
                "authorization_required": True,
                "authorization_status": "approved",
                "appointment_scheduled": False,
                "patient_contacted": True,
                "estimated_completion": "2024-01-25"
            },
            "communication_log": [
                {
                    "date": "2024-01-15T09:00:00Z",
                    "action": "referral_submitted",
                    "party": "referring_provider"
                },
                {
                    "date": "2024-01-15T10:30:00Z",
                    "action": "insurance_verified",
                    "party": "referral_coordinator"
                }
            ]
        }
    },

    "hie_integration": {
        "name": "Health Information Exchange Integration",
        "description": "Health Information Exchange connectivity for cross-provider data sharing and interoperability",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "hie_networks": {"type": "array", "description": "HIE networks to query", "enum": ["CommonWell", "Carequality", "Regional_HIE", "all"]},
            "data_categories": {"type": "array", "description": "Categories of data to retrieve"},
            "consent_status": {"type": "string", "description": "Patient consent status", "enum": ["active", "verify_required"]}
        },
        "mock_response": {
            "hie_query_id": "HIE_20240115_001",
            "patient_id": "PAT789012",
            "networks_queried": ["CommonWell", "Carequality", "Metro Regional HIE"],
            "consent_verified": True,
            "participating_organizations": [
                {
                    "organization": "Metro Hospital System",
                    "network": "CommonWell",
                    "data_available": ["encounters", "medications", "allergies", "lab_results"],
                    "last_activity": "2024-01-10"
                },
                {
                    "organization": "Regional Medical Center",
                    "network": "Carequality",
                    "data_available": ["emergency_visits", "radiology", "discharge_summaries"],
                    "last_activity": "2024-01-08"
                },
                {
                    "organization": "Community Health Partners",
                    "network": "Metro Regional HIE",
                    "data_available": ["primary_care_visits", "preventive_care", "immunizations"],
                    "last_activity": "2024-01-12"
                }
            ],
            "consolidated_data": {
                "encounters_summary": {
                    "total_encounters": 15,
                    "emergency_visits": 2,
                    "inpatient_stays": 1,
                    "outpatient_visits": 12,
                    "date_range": "2023-01-01 to 2024-01-15"
                },
                "medications_reconciled": 8,
                "allergies_consolidated": 3,
                "immunizations_current": True
            },
            "data_quality_metrics": {
                "completeness": 0.87,
                "timeliness": 0.92,
                "accuracy_score": 0.89,
                "duplicate_entries": 4
            },
            "privacy_compliance": {
                "consent_documented": True,
                "minimum_necessary_applied": True,
                "audit_trail_complete": True,
                "data_retention_policy": "7 years"
            }
        }
    },

    "care_management_platforms": {
        "name": "Care Management Platform Integration",
        "description": "Comprehensive care coordination platform for care plans, team communication, and outcome tracking",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "care_plan_type": {"type": "string", "description": "Type of care plan", "enum": ["chronic_disease", "post_acute", "transitional", "wellness", "all"]},
            "team_member_role": {"type": "string", "description": "Care team member role filter"},
            "include_outcomes": {"type": "boolean", "description": "Include outcome measurements"}
        },
        "mock_response": {
            "care_management_id": "CM_20240115_001",
            "patient_id": "PAT789012",
            "active_care_plans": [
                {
                    "plan_id": "CP_DIABETES_001",
                    "plan_type": "chronic_disease",
                    "condition": "Type 2 Diabetes",
                    "start_date": "2023-06-15",
                    "status": "active",
                    "care_manager": "Sarah Johnson, RN",
                    "next_review": "2024-03-15"
                },
                {
                    "plan_id": "CP_HTN_001",
                    "plan_type": "chronic_disease",
                    "condition": "Hypertension",
                    "start_date": "2023-08-01",
                    "status": "active",
                    "care_manager": "Mike Chen, PharmD",
                    "next_review": "2024-02-01"
                }
            ],
            "care_team": [
                {
                    "role": "Primary Care Provider",
                    "name": "Dr. Jane Smith",
                    "contact": "jsmith@primarycare.com",
                    "last_contact": "2024-01-10"
                },
                {
                    "role": "Care Manager",
                    "name": "Sarah Johnson, RN",
                    "contact": "sjohnson@caremanagement.com",
                    "last_contact": "2024-01-12"
                },
                {
                    "role": "Pharmacist",
                    "name": "Mike Chen, PharmD",
                    "contact": "mchen@pharmacy.com",
                    "last_contact": "2024-01-08"
                }
            ],
            "risk_stratification": {
                "overall_risk_score": 72,
                "risk_category": "moderate",
                "primary_risk_factors": ["diabetes_control", "medication_adherence", "social_determinants"],
                "intervention_priority": "medium"
            },
            "outcome_measures": {
                "hba1c_trend": "improving",
                "blood_pressure_control": "adequate",
                "medication_adherence_score": 0.78,
                "patient_engagement_score": 0.85,
                "quality_measures_met": 7,
                "quality_measures_total": 10
            },
            "recent_interactions": [
                {
                    "date": "2024-01-12",
                    "type": "care_coordination_call",
                    "participant": "Sarah Johnson, RN",
                    "summary": "Reviewed medication adherence, scheduled lab work",
                    "action_items": ["Schedule HbA1c test", "Med adherence counseling"]
                }
            ]
        }
    },

    # MEDIUM PRIORITY: Claims & Analytics Tools
    "qnext_auth_history": {
        "name": "QNext Authorization History",
        "description": "QNext platform authorization history and prior authorization tracking system",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "auth_number": {"type": "string", "description": "Specific authorization number (optional)"},
            "date_range": {"type": "string", "description": "Date range for authorization history"},
            "status_filter": {"type": "string", "description": "Authorization status filter", "enum": ["approved", "denied", "pending", "expired", "all"]}
        },
        "mock_response": {
            "member_id": "MEM789012345",
            "query_period": "2023-01-01 to 2024-01-15",
            "total_authorizations": 23,
            "authorization_summary": {
                "approved": 18,
                "denied": 3,
                "pending": 1,
                "expired": 1
            },
            "authorization_history": [
                {
                    "auth_number": "QNEXT_AUTH_001234",
                    "service_code": "77058",
                    "service_description": "Mammography, bilateral",
                    "status": "approved",
                    "approved_date": "2024-01-10",
                    "valid_from": "2024-01-15",
                    "valid_to": "2024-07-15",
                    "authorized_units": 1,
                    "units_used": 0,
                    "provider_name": "Metro Imaging Center",
                    "medical_necessity": "routine_screening"
                },
                {
                    "auth_number": "QNEXT_AUTH_001235",
                    "service_code": "93306",
                    "service_description": "Echocardiography",
                    "status": "approved",
                    "approved_date": "2024-01-05",
                    "valid_from": "2024-01-08",
                    "valid_to": "2024-04-08",
                    "authorized_units": 1,
                    "units_used": 1,
                    "provider_name": "Cardiology Associates",
                    "medical_necessity": "abnormal_ekg"
                }
            ],
            "utilization_metrics": {
                "authorization_approval_rate": 0.87,
                "average_approval_time_days": 2.5,
                "utilization_rate": 0.78,
                "most_common_services": ["imaging", "specialty_consultations", "procedures"]
            },
            "recent_trends": {
                "monthly_authorization_volume": "stable",
                "approval_rate_trend": "improving",
                "denial_reasons": ["insufficient_documentation", "not_medically_necessary", "experimental"]
            }
        }
    },

    "claims_history": {
        "name": "Claims History Access",
        "description": "Comprehensive claims history database for member claims tracking and analysis",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "claim_type": {"type": "string", "description": "Type of claim", "enum": ["medical", "pharmacy", "dental", "vision", "all"]},
            "date_range": {"type": "string", "description": "Date range for claims history"},
            "status_filter": {"type": "string", "description": "Claim status filter", "enum": ["paid", "denied", "pending", "all"]}
        },
        "mock_response": {
            "member_id": "MEM789012345",
            "claims_period": "2023-01-01 to 2024-01-15",
            "total_claims": 47,
            "claims_summary": {
                "medical_claims": 32,
                "pharmacy_claims": 12,
                "dental_claims": 2,
                "vision_claims": 1
            },
            "financial_summary": {
                "total_billed": 24567.89,
                "total_paid": 19234.56,
                "member_responsibility": 2890.34,
                "savings": 2442.99
            },
            "recent_claims": [
                {
                    "claim_number": "CLM_20240110_001",
                    "service_date": "2024-01-10",
                    "provider": "Metro Medical Center",
                    "service_description": "Office Visit - Level 3",
                    "procedure_codes": ["99213"],
                    "billed_amount": 245.00,
                    "allowed_amount": 180.00,
                    "paid_amount": 155.00,
                    "member_responsibility": 25.00,
                    "status": "paid",
                    "payment_date": "2024-01-12"
                },
                {
                    "claim_number": "CLM_20240108_001",
                    "service_date": "2024-01-08",
                    "provider": "Regional Pharmacy",
                    "service_description": "Prescription - Metformin",
                    "ndc_code": "00093-0058-01",
                    "billed_amount": 65.00,
                    "allowed_amount": 45.00,
                    "paid_amount": 35.00,
                    "member_responsibility": 10.00,
                    "status": "paid",
                    "payment_date": "2024-01-09"
                }
            ],
            "utilization_patterns": {
                "primary_care_visits": 8,
                "specialist_visits": 4,
                "emergency_visits": 1,
                "prescriptions_filled": 24,
                "preventive_care_compliance": 0.85
            },
            "cost_analysis": {
                "average_claim_amount": 522.51,
                "highest_cost_categories": ["imaging", "specialist_procedures", "brand_medications"],
                "cost_trend": "stable",
                "cost_per_member_per_month": 1269.45
            }
        }
    },

    "benefit_calculator": {
        "name": "Benefits Calculation Tool",
        "description": "Advanced benefits calculation engine for deductibles, coinsurance, and out-of-pocket maximums",
        "input_schema": {
            "member_id": {"type": "string", "description": "Member identifier"},
            "service_codes": {"type": "array", "description": "List of service codes for calculation"},
            "service_amounts": {"type": "array", "description": "Corresponding billed amounts"},
            "calculation_type": {"type": "string", "description": "Type of calculation", "enum": ["estimate", "actual", "what_if"]}
        },
        "mock_response": {
            "calculation_id": "CALC_20240115_001",
            "member_id": "MEM789012345",
            "plan_year": "2024",
            "current_accumulations": {
                "deductible_met": 1200.00,
                "deductible_remaining": 300.00,
                "out_of_pocket_met": 2450.00,
                "out_of_pocket_remaining": 3550.00
            },
            "service_calculations": [
                {
                    "service_code": "99214",
                    "service_description": "Office Visit - Level 4",
                    "billed_amount": 350.00,
                    "allowed_amount": 280.00,
                    "deductible_applied": 280.00,
                    "coinsurance_amount": 0.00,
                    "copay_amount": 0.00,
                    "member_responsibility": 280.00,
                    "plan_pays": 0.00
                },
                {
                    "service_code": "80053",
                    "service_description": "Comprehensive Metabolic Panel",
                    "billed_amount": 125.00,
                    "allowed_amount": 95.00,
                    "deductible_applied": 20.00,
                    "coinsurance_amount": 15.00,
                    "copay_amount": 0.00,
                    "member_responsibility": 35.00,
                    "plan_pays": 60.00
                }
            ],
            "total_calculation": {
                "total_billed": 475.00,
                "total_allowed": 375.00,
                "total_member_responsibility": 315.00,
                "total_plan_pays": 60.00,
                "savings_vs_billed": 100.00
            },
            "updated_accumulations": {
                "new_deductible_met": 1500.00,
                "new_deductible_remaining": 0.00,
                "new_out_of_pocket_met": 2765.00,
                "new_out_of_pocket_remaining": 3235.00,
                "deductible_satisfied": True
            },
            "benefit_explanations": [
                "Deductible will be satisfied after these services",
                "Future services will be subject to 20% coinsurance",
                "Out-of-pocket maximum is $6,000 for individual coverage"
            ]
        }
    },

    "data_transformer": {
        "name": "Data Transformation Tool",
        "description": "Advanced data transformation and standardization engine for healthcare data processing",
        "input_schema": {
            "input_data": {"type": "object", "description": "Raw input data to be transformed"},
            "transformation_type": {"type": "string", "description": "Type of transformation", "enum": ["hl7_to_fhir", "claims_to_clinical", "standardize", "aggregate", "custom"]},
            "output_format": {"type": "string", "description": "Desired output format", "enum": ["fhir", "hl7", "json", "xml", "csv"]},
            "validation_rules": {"type": "array", "description": "Validation rules to apply"}
        },
        "mock_response": {
            "transformation_id": "TRANS_20240115_001",
            "input_records": 1247,
            "output_records": 1243,
            "transformation_summary": {
                "records_processed": 1247,
                "records_transformed": 1243,
                "records_failed": 4,
                "records_skipped": 0,
                "processing_time_seconds": 8.7
            },
            "data_quality_metrics": {
                "completeness_score": 0.94,
                "accuracy_score": 0.97,
                "consistency_score": 0.91,
                "validity_score": 0.96
            },
            "transformation_details": {
                "field_mappings_applied": 47,
                "data_type_conversions": 23,
                "value_standardizations": 156,
                "validation_rules_passed": 12,
                "validation_rules_failed": 2
            },
            "output_sample": {
                "resource_type": "Patient",
                "id": "patient-123456",
                "identifier": [
                    {
                        "system": "http://hospital.example.org/mrn",
                        "value": "MRN123456"
                    }
                ],
                "name": [
                    {
                        "family": "Smith",
                        "given": ["John", "Michael"]
                    }
                ],
                "gender": "male",
                "birthDate": "1975-08-15"
            },
            "validation_results": [
                {
                    "rule": "required_fields_present",
                    "status": "passed",
                    "details": "All required fields validated successfully"
                },
                {
                    "rule": "date_format_validation",
                    "status": "failed",
                    "details": "4 records had invalid date formats",
                    "affected_records": ["REC001", "REC045", "REC089", "REC234"]
                }
            ],
            "performance_metrics": {
                "throughput_records_per_second": 143.4,
                "memory_usage_mb": 256.7,
                "cpu_utilization_percent": 23.5
            }
        }
    },

    "ml_theme_extraction": {
        "name": "ML Theme Extraction Engine",
        "description": "Machine learning-powered theme extraction and categorization for patient feedback analysis",
        "input_schema": {
            "text_data": {"type": "array", "description": "Array of text content for analysis"},
            "analysis_depth": {"type": "string", "description": "Depth of analysis", "enum": ["basic", "detailed", "comprehensive"]},
            "domain_focus": {"type": "string", "description": "Healthcare domain focus", "enum": ["patient_experience", "clinical_quality", "operations", "all"]},
            "language": {"type": "string", "description": "Primary language of text content"}
        },
        "mock_response": {
            "analysis_id": "ML_THEME_20240115_001",
            "documents_processed": 2847,
            "processing_time_seconds": 12.4,
            "theme_extraction_results": {
                "primary_themes": [
                    {
                        "theme": "wait_times",
                        "frequency": 0.42,
                        "sentiment": "negative",
                        "confidence_score": 0.89,
                        "related_keywords": ["waiting", "delay", "appointment", "late", "schedule"],
                        "impact_score": "high"
                    },
                    {
                        "theme": "staff_communication",
                        "frequency": 0.38,
                        "sentiment": "positive",
                        "confidence_score": 0.91,
                        "related_keywords": ["friendly", "helpful", "explained", "listened", "caring"],
                        "impact_score": "high"
                    },
                    {
                        "theme": "facility_cleanliness",
                        "frequency": 0.31,
                        "sentiment": "positive",
                        "confidence_score": 0.94,
                        "related_keywords": ["clean", "sanitized", "hygienic", "maintained", "organized"],
                        "impact_score": "medium"
                    }
                ],
                "emerging_themes": [
                    {
                        "theme": "telehealth_experience",
                        "frequency": 0.15,
                        "sentiment": "mixed",
                        "confidence_score": 0.76,
                        "trend": "increasing"
                    },
                    {
                        "theme": "parking_availability",
                        "frequency": 0.12,
                        "sentiment": "negative",
                        "confidence_score": 0.82,
                        "trend": "stable"
                    }
                ]
            },
            "sentiment_analysis": {
                "overall_sentiment": 0.73,
                "sentiment_distribution": {
                    "very_positive": 0.28,
                    "positive": 0.34,
                    "neutral": 0.23,
                    "negative": 0.12,
                    "very_negative": 0.03
                },
                "sentiment_trends": {
                    "improving_areas": ["provider_communication", "appointment_scheduling"],
                    "declining_areas": ["wait_times", "insurance_processes"]
                }
            },
            "actionable_insights": [
                {
                    "insight": "Implement real-time wait time notifications",
                    "theme": "wait_times",
                    "priority": "high",
                    "estimated_impact": "25% reduction in wait time complaints"
                },
                {
                    "insight": "Expand staff communication training program",
                    "theme": "staff_communication",
                    "priority": "medium",
                    "estimated_impact": "15% improvement in satisfaction scores"
                }
            ],
            "model_performance": {
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.91,
                "f1_score": 0.90,
                "model_version": "healthcare_nlp_v2.3"
            }
        }
    },

    # LOWER PRIORITY: Specialized Tools
    "healthcare_claims_database": {
        "name": "Healthcare Claims Database",
        "description": "Comprehensive claims database for historical claims analysis and pattern recognition",
        "input_schema": {
            "query_type": {"type": "string", "description": "Type of query", "enum": ["member_history", "provider_patterns", "service_utilization", "cost_analysis"]},
            "filters": {"type": "object", "description": "Query filters (member_id, date_range, service_codes, etc.)"},
            "aggregation_level": {"type": "string", "description": "Aggregation level", "enum": ["individual", "group", "population"]}
        },
        "mock_response": {
            "query_id": "CLAIMS_DB_20240115_001",
            "query_execution_time_ms": 847,
            "records_found": 15647,
            "aggregated_results": {
                "total_claims_analyzed": 15647,
                "total_members": 3241,
                "date_range": "2022-01-01 to 2024-01-15",
                "financial_summary": {
                    "total_billed_amount": 12456789.45,
                    "total_paid_amount": 9234567.89,
                    "average_claim_amount": 795.43
                }
            },
            "utilization_patterns": {
                "most_common_services": [
                    {"service": "Office Visits", "frequency": 0.34, "avg_cost": 185.50},
                    {"service": "Laboratory Tests", "frequency": 0.28, "avg_cost": 125.30},
                    {"service": "Pharmacy", "frequency": 0.22, "avg_cost": 89.75}
                ],
                "seasonal_trends": {
                    "peak_months": ["January", "February", "March"],
                    "lowest_months": ["July", "August"]
                },
                "geographic_distribution": {
                    "urban": 0.68,
                    "suburban": 0.24,
                    "rural": 0.08
                }
            },
            "cost_analysis": {
                "high_cost_members": 156,
                "high_cost_threshold": 50000,
                "cost_drivers": ["chronic_conditions", "specialty_drugs", "emergency_visits"],
                "cost_trend": "increasing_moderate"
            },
            "quality_indicators": {
                "preventive_care_compliance": 0.76,
                "chronic_disease_management": 0.82,
                "emergency_department_utilization": 0.23
            }
        }
    },

    "insurance_plan_rules": {
        "name": "Insurance Plan Rules Engine",
        "description": "Comprehensive insurance plan rules and coverage determination engine",
        "input_schema": {
            "plan_id": {"type": "string", "description": "Insurance plan identifier"},
            "service_codes": {"type": "array", "description": "Service codes to evaluate"},
            "member_id": {"type": "string", "description": "Member identifier"},
            "rule_category": {"type": "string", "description": "Rule category", "enum": ["coverage", "prior_auth", "quantity_limits", "step_therapy", "all"]}
        },
        "mock_response": {
            "plan_id": "PLAN_PPO_2024",
            "plan_name": "Health Plus PPO",
            "effective_date": "2024-01-01",
            "rule_evaluation_results": [
                {
                    "service_code": "99214",
                    "service_description": "Office Visit - Level 4",
                    "coverage_determination": "covered",
                    "coverage_percentage": 80,
                    "prior_authorization_required": False,
                    "quantity_limits": {
                        "limit_applies": False,
                        "limit_description": "No limit on office visits"
                    },
                    "member_cost_share": {
                        "copay": 0,
                        "coinsurance": 20,
                        "applies_to_deductible": True
                    }
                },
                {
                    "service_code": "J0585",
                    "service_description": "Botulinum Toxin Injection",
                    "coverage_determination": "covered_with_conditions",
                    "coverage_percentage": 80,
                    "prior_authorization_required": True,
                    "conditions": [
                        "Medical necessity documentation required",
                        "Failure of conservative therapy",
                        "Specific diagnosis codes required"
                    ],
                    "quantity_limits": {
                        "limit_applies": True,
                        "limit_description": "Maximum 4 treatments per year",
                        "current_usage": 1,
                        "remaining_allowance": 3
                    }
                }
            ],
            "plan_benefits_summary": {
                "deductible": {
                    "individual": 1500,
                    "family": 3000
                },
                "out_of_pocket_maximum": {
                    "individual": 6000,
                    "family": 12000
                },
                "coinsurance": 20,
                "network_type": "PPO"
            },
            "special_programs": {
                "wellness_incentives": True,
                "disease_management": ["diabetes", "hypertension", "asthma"],
                "preventive_care_covered": True,
                "telemedicine_coverage": True
            }
        }
    },

    "healthcare_facility_directory": {
        "name": "Healthcare Facility Directory",
        "description": "Comprehensive healthcare facility and provider directory with specialties and network status",
        "input_schema": {
            "search_criteria": {"type": "object", "description": "Search criteria (location, specialty, network, etc.)"},
            "search_radius_miles": {"type": "integer", "description": "Search radius in miles"},
            "include_availability": {"type": "boolean", "description": "Include real-time availability"},
            "network_filter": {"type": "string", "description": "Network filter", "enum": ["in_network", "out_of_network", "all"]}
        },
        "mock_response": {
            "search_id": "DIR_SEARCH_20240115_001",
            "search_criteria": {
                "specialty": "Cardiology",
                "location": "Metro City",
                "radius_miles": 25,
                "network_status": "in_network"
            },
            "total_results": 23,
            "facilities": [
                {
                    "facility_id": "FAC_001",
                    "name": "Metro Heart & Vascular Center",
                    "address": "123 Medical Plaza Dr, Metro City, ST 12345",
                    "phone": "555-123-4567",
                    "network_status": "in_network",
                    "distance_miles": 3.2,
                    "specialties": ["Cardiology", "Cardiac Surgery", "Interventional Cardiology"],
                    "providers": [
                        {
                            "name": "Dr. Michael Chen",
                            "npi": "1234567890",
                            "specialty": "Interventional Cardiology",
                            "accepting_new_patients": True,
                            "next_available": "2024-01-22T09:00:00Z"
                        },
                        {
                            "name": "Dr. Sarah Williams",
                            "npi": "0987654321",
                            "specialty": "Cardiology",
                            "accepting_new_patients": True,
                            "next_available": "2024-01-25T14:30:00Z"
                        }
                    ],
                    "facility_features": {
                        "parking_available": True,
                        "wheelchair_accessible": True,
                        "languages_supported": ["English", "Spanish", "Mandarin"],
                        "imaging_services": True,
                        "lab_services": True
                    },
                    "quality_ratings": {
                        "cms_star_rating": 4.5,
                        "patient_satisfaction": 4.3,
                        "safety_rating": "A"
                    }
                }
            ],
            "search_suggestions": [
                "Consider expanding search radius to 50 miles for more options",
                "Alternative specialties: Internal Medicine with cardiology subspecialty",
                "Telehealth options available for some consultations"
            ],
            "network_coverage_info": {
                "in_network_facilities": 18,
                "out_of_network_facilities": 5,
                "coverage_gaps": "Limited interventional cardiology options in rural areas"
            }
        }
    },

    "navigation_ml_analytics": {
        "name": "Navigation ML Analytics Platform",
        "description": "Machine learning analytics platform for healthcare navigation patterns and optimization insights",
        "input_schema": {
            "analytics_type": {"type": "string", "description": "Type of analytics", "enum": ["patient_journeys", "navigation_patterns", "bottleneck_analysis", "outcome_prediction"]},
            "time_period": {"type": "string", "description": "Analysis time period"},
            "patient_cohort": {"type": "string", "description": "Patient cohort filter"},
            "include_predictions": {"type": "boolean", "description": "Include predictive analytics"}
        },
        "mock_response": {
            "analytics_id": "NAV_ML_20240115_001",
            "analysis_period": "2023-07-01 to 2024-01-15",
            "patient_journeys_analyzed": 8734,
            "navigation_insights": {
                "common_pathways": [
                    {
                        "pathway": "PCP → Specialist → Procedure → Follow-up",
                        "frequency": 0.34,
                        "average_time_to_completion_days": 45,
                        "success_rate": 0.87
                    },
                    {
                        "pathway": "Emergency → Admission → Discharge → PCP",
                        "frequency": 0.18,
                        "average_time_to_completion_days": 21,
                        "success_rate": 0.76
                    }
                ],
                "bottleneck_analysis": {
                    "appointment_scheduling": {
                        "average_wait_time_days": 12.5,
                        "impact_on_outcomes": "moderate",
                        "improvement_potential": "high"
                    },
                    "insurance_authorization": {
                        "average_processing_time_days": 3.8,
                        "impact_on_outcomes": "low",
                        "improvement_potential": "medium"
                    },
                    "test_result_communication": {
                        "average_delay_days": 2.1,
                        "impact_on_outcomes": "high",
                        "improvement_potential": "high"
                    }
                }
            },
            "predictive_analytics": {
                "care_gap_predictions": [
                    {
                        "gap_type": "missed_preventive_care",
                        "predicted_patients": 234,
                        "confidence": 0.89,
                        "intervention_window_days": 30
                    },
                    {
                        "gap_type": "medication_adherence_decline",
                        "predicted_patients": 156,
                        "confidence": 0.82,
                        "intervention_window_days": 14
                    }
                ],
                "outcome_predictions": {
                    "readmission_risk": {
                        "high_risk_patients": 67,
                        "prediction_accuracy": 0.84,
                        "primary_risk_factors": ["multiple_comorbidities", "social_determinants", "medication_complexity"]
                    },
                    "navigation_success": {
                        "completion_probability": 0.78,
                        "key_success_factors": ["care_coordination", "patient_engagement", "provider_communication"]
                    }
                }
            },
            "optimization_recommendations": [
                {
                    "recommendation": "Implement proactive appointment scheduling for high-risk patients",
                    "impact_area": "appointment_scheduling",
                    "estimated_improvement": "25% reduction in wait times",
                    "implementation_priority": "high"
                },
                {
                    "recommendation": "Deploy automated test result notifications",
                    "impact_area": "communication",
                    "estimated_improvement": "60% faster result delivery",
                    "implementation_priority": "medium"
                }
            ],
            "model_performance": {
                "prediction_accuracy": 0.86,
                "data_quality_score": 0.91,
                "model_confidence": 0.83,
                "last_training_date": "2024-01-01"
            }
        }
    },

    # NEW MCP TOOLS FOR PROVIDER ENABLEMENT & UTILIZATION MANAGEMENT

    # Provider Enablement - Compliance Documentation Tools
    "provider_notes_api": {
        "name": "Provider Notes API Access",
        "description": "Access provider clinical notes and documentation from EHR systems for compliance auditing",
        "input_schema": {
            "provider_id": {"type": "string", "description": "Provider identifier or NPI"},
            "date_range": {"type": "string", "description": "Date range for notes retrieval"},
            "note_type": {"type": "string", "description": "Type of clinical notes", "enum": ["progress", "assessment", "procedure", "discharge", "all"]},
            "compliance_scope": {"type": "string", "description": "Compliance scope", "enum": ["full", "attestation_only", "template_check"]}
        },
        "mock_response": {
            "provider_id": "NPI_1234567890",
            "provider_name": "Dr. Sarah Johnson, MD",
            "notes_retrieved": 234,
            "date_range": "2024-09-11 to 2024-10-11",
            "clinical_notes": [
                {
                    "note_id": "NOTE_20241011_001",
                    "note_type": "progress",
                    "patient_id": "PAT123456",
                    "date_created": "2024-10-11T09:30:00Z",
                    "content": "Patient continues to show improvement with current treatment plan. Vital signs stable.",
                    "attestation_status": "complete",
                    "template_compliance": 0.92,
                    "required_elements": ["assessment", "plan", "signature", "date"],
                    "missing_elements": []
                },
                {
                    "note_id": "NOTE_20241010_003",
                    "note_type": "assessment",
                    "patient_id": "PAT123457",
                    "date_created": "2024-10-10T14:15:00Z",
                    "content": "Initial assessment reveals acute condition requiring immediate intervention.",
                    "attestation_status": "incomplete",
                    "template_compliance": 0.67,
                    "required_elements": ["assessment", "plan", "signature", "date", "medical_necessity"],
                    "missing_elements": ["medical_necessity", "signature"]
                }
            ],
            "compliance_summary": {
                "total_notes": 234,
                "compliant_notes": 198,
                "compliance_rate": 0.846,
                "common_missing_elements": ["signature", "medical_necessity", "follow_up_plan"]
            }
        }
    },

    "audit_database_connector": {
        "name": "Audit Database Connector",
        "description": "Access historical audit data and compliance templates for comparison analysis",
        "input_schema": {
            "provider_id": {"type": "string", "description": "Provider identifier"},
            "audit_type": {"type": "string", "description": "Type of audit", "enum": ["compliance", "quality", "utilization", "all"]},
            "time_period": {"type": "string", "description": "Time period for audit history"},
            "template_category": {"type": "string", "description": "Template category filter"}
        },
        "mock_response": {
            "provider_id": "NPI_1234567890",
            "audit_history": [
                {
                    "audit_id": "AUDIT_20241001_001",
                    "audit_type": "compliance",
                    "audit_date": "2024-10-01",
                    "compliance_score": 0.88,
                    "findings": 12,
                    "critical_issues": 2,
                    "status": "resolved",
                    "follow_up_required": False
                },
                {
                    "audit_id": "AUDIT_20240901_001",
                    "audit_type": "quality",
                    "audit_date": "2024-09-01",
                    "compliance_score": 0.92,
                    "findings": 8,
                    "critical_issues": 0,
                    "status": "closed",
                    "follow_up_required": False
                }
            ],
            "compliance_templates": [
                {
                    "template_id": "TEMP_CMS_001",
                    "template_name": "CMS Documentation Requirements",
                    "version": "2024.1",
                    "required_elements": ["patient_id", "diagnosis", "treatment_plan", "provider_signature", "date"],
                    "optional_elements": ["family_history", "social_history"],
                    "compliance_criteria": {
                        "minimum_score": 0.85,
                        "required_element_weight": 0.7,
                        "documentation_quality_weight": 0.3
                    }
                }
            ],
            "audit_trends": {
                "compliance_trend": "improving",
                "average_score_last_6_months": 0.89,
                "most_common_issues": ["missing_signatures", "incomplete_assessment", "inadequate_documentation"]
            }
        }
    },

    "healthcare_compliance_nlp": {
        "name": "Healthcare Compliance NLP Processor",
        "description": "Advanced NLP engine specialized for healthcare compliance analysis and attestation element identification",
        "input_schema": {
            "document_text": {"type": "string", "description": "Clinical document text for analysis"},
            "analysis_type": {"type": "string", "description": "Type of analysis", "enum": ["attestation", "compliance", "template_match", "all"]},
            "regulatory_standard": {"type": "string", "description": "Regulatory standard", "enum": ["CMS", "Joint_Commission", "HIPAA", "all"]},
            "confidence_threshold": {"type": "float", "description": "Minimum confidence for element identification"}
        },
        "mock_response": {
            "analysis_id": "NLP_COMP_20241011_001",
            "document_length": 1247,
            "processing_time_ms": 892,
            "attestation_elements": {
                "identified_elements": [
                    {"element": "patient_identification", "confidence": 0.98, "location": "header"},
                    {"element": "chief_complaint", "confidence": 0.94, "location": "paragraph_1"},
                    {"element": "assessment", "confidence": 0.92, "location": "paragraph_3"},
                    {"element": "treatment_plan", "confidence": 0.89, "location": "paragraph_4"}
                ],
                "missing_elements": [
                    {"element": "provider_signature", "required": True, "criticality": "high"},
                    {"element": "medical_necessity", "required": True, "criticality": "medium"}
                ]
            },
            "compliance_analysis": {
                "overall_compliance_score": 0.76,
                "regulatory_adherence": {
                    "CMS": 0.78,
                    "Joint_Commission": 0.82,
                    "HIPAA": 0.95
                },
                "documentation_quality": {
                    "completeness": 0.74,
                    "clarity": 0.88,
                    "medical_terminology_accuracy": 0.96
                }
            },
            "recommendations": [
                "Add provider electronic signature to meet CMS requirements",
                "Include explicit medical necessity statement",
                "Improve documentation completeness for better compliance scores"
            ]
        }
    },

    "template_matching_engine": {
        "name": "Template Matching Engine",
        "description": "Machine learning-powered template matching for compliance standards verification",
        "input_schema": {
            "document_content": {"type": "string", "description": "Document content for template matching"},
            "template_library": {"type": "array", "description": "Template library to match against"},
            "matching_algorithm": {"type": "string", "description": "Matching algorithm", "enum": ["semantic", "structural", "hybrid"]},
            "match_threshold": {"type": "float", "description": "Minimum match score threshold"}
        },
        "mock_response": {
            "matching_id": "MATCH_20241011_001",
            "document_id": "DOC_12345",
            "template_matches": [
                {
                    "template_id": "TEMP_PROGRESS_NOTE_001",
                    "template_name": "Standard Progress Note Template",
                    "match_score": 0.94,
                    "confidence": 0.91,
                    "matched_sections": [
                        {"section": "subjective", "match_score": 0.96},
                        {"section": "objective", "match_score": 0.93},
                        {"section": "assessment", "match_score": 0.92},
                        {"section": "plan", "match_score": 0.95}
                    ],
                    "missing_sections": [],
                    "compliance_rating": "excellent"
                },
                {
                    "template_id": "TEMP_CMS_EVAL_001",
                    "template_name": "CMS Evaluation Template",
                    "match_score": 0.87,
                    "confidence": 0.84,
                    "matched_sections": [
                        {"section": "history", "match_score": 0.89},
                        {"section": "examination", "match_score": 0.91},
                        {"section": "decision_making", "match_score": 0.81}
                    ],
                    "missing_sections": ["medical_necessity_statement"],
                    "compliance_rating": "good"
                }
            ],
            "best_match": {
                "template_id": "TEMP_PROGRESS_NOTE_001",
                "overall_score": 0.94,
                "recommendation": "Document follows standard progress note format well"
            },
            "improvement_suggestions": [
                "Consider adding medical necessity statement for CMS compliance",
                "Enhance objective findings documentation",
                "Include specific follow-up timeline"
            ]
        }
    },

    # Utilization Management - Healthcare System Integration Tools
    "his_integration": {
        "name": "Hospital Information System Integration",
        "description": "Access comprehensive hospital information system data for patient records and clinical information",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "admission_id": {"type": "string", "description": "Hospital admission identifier"},
            "data_scope": {"type": "string", "description": "Scope of data", "enum": ["admission", "clinical", "financial", "all"]},
            "include_realtime": {"type": "boolean", "description": "Include real-time data updates"}
        },
        "mock_response": {
            "patient_id": "PAT789012",
            "admission_id": "ADM_20241005_001",
            "admission_details": {
                "admission_date": "2024-10-05T08:30:00Z",
                "admission_type": "emergency",
                "attending_physician": "Dr. Michael Chen",
                "primary_diagnosis": "Community-acquired pneumonia",
                "secondary_diagnoses": ["Hypertension", "Type 2 diabetes"],
                "current_location": "Medical Floor - Room 234B",
                "length_of_stay_days": 6
            },
            "clinical_status": {
                "current_condition": "stable",
                "activity_level": "ambulating_with_assistance",
                "diet_orders": "regular_diet",
                "oxygen_requirement": "room_air",
                "iv_access": "saline_lock",
                "isolation_precautions": "standard"
            },
            "care_team": [
                {"role": "attending_physician", "name": "Dr. Michael Chen", "service": "internal_medicine"},
                {"role": "resident", "name": "Dr. Sarah Kim", "service": "internal_medicine"},
                {"role": "nurse", "name": "Jennifer Lopez, RN", "unit": "4_west"},
                {"role": "case_manager", "name": "Maria Santos, MSW", "department": "utilization_management"}
            ],
            "utilization_metrics": {
                "expected_los": 4,
                "current_los": 6,
                "variance_days": 2,
                "acuity_score": 65,
                "discharge_barriers": ["awaiting_skilled_nursing_placement"],
                "estimated_discharge_date": "2024-10-12"
            }
        }
    },

    "ehr_clinical_data": {
        "name": "EHR Clinical Data Access",
        "description": "Access electronic health record systems for detailed clinical information and patient history",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "data_categories": {"type": "array", "description": "Clinical data categories to retrieve"},
            "time_range": {"type": "string", "description": "Time range for clinical data"},
            "include_trends": {"type": "boolean", "description": "Include trending data analysis"}
        },
        "mock_response": {
            "patient_id": "PAT789012",
            "medical_history": {
                "allergies": [
                    {"allergen": "Penicillin", "reaction": "Rash", "severity": "moderate"},
                    {"allergen": "Shellfish", "reaction": "Anaphylaxis", "severity": "severe"}
                ],
                "chronic_conditions": [
                    {"condition": "Hypertension", "onset_date": "2018-03-15", "status": "controlled"},
                    {"condition": "Type 2 Diabetes", "onset_date": "2020-07-22", "status": "controlled"},
                    {"condition": "Hyperlipidemia", "onset_date": "2019-11-08", "status": "controlled"}
                ],
                "surgical_history": [
                    {"procedure": "Cholecystectomy", "date": "2021-05-14", "surgeon": "Dr. Williams"}
                ]
            },
            "current_medications": [
                {"medication": "Lisinopril 10mg", "frequency": "daily", "start_date": "2024-01-15"},
                {"medication": "Metformin 500mg", "frequency": "twice_daily", "start_date": "2024-01-15"},
                {"medication": "Atorvastatin 20mg", "frequency": "daily", "start_date": "2024-01-15"}
            ],
            "recent_vitals": {
                "blood_pressure": {"systolic": 128, "diastolic": 82, "timestamp": "2024-10-11T08:00:00Z"},
                "heart_rate": {"value": 76, "rhythm": "regular", "timestamp": "2024-10-11T08:00:00Z"},
                "temperature": {"value": 98.6, "route": "oral", "timestamp": "2024-10-11T08:00:00Z"},
                "oxygen_saturation": {"value": 98, "room_air": True, "timestamp": "2024-10-11T08:00:00Z"}
            },
            "clinical_trends": {
                "vital_signs_stability": "stable_last_24h",
                "pain_score_trend": "decreasing",
                "functional_status": "improving",
                "laboratory_trends": "normalizing"
            }
        }
    },

    "lis_integration": {
        "name": "Laboratory Information System Integration",
        "description": "Access laboratory information systems for lab results and diagnostic data analysis",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "test_categories": {"type": "array", "description": "Laboratory test categories"},
            "date_range": {"type": "string", "description": "Date range for lab results"},
            "include_critical_values": {"type": "boolean", "description": "Include critical value alerts"}
        },
        "mock_response": {
            "patient_id": "PAT789012",
            "lab_results": [
                {
                    "test_name": "Complete Blood Count",
                    "collection_date": "2024-10-11T06:00:00Z",
                    "resulted_date": "2024-10-11T08:30:00Z",
                    "results": {
                        "wbc": {"value": 8.2, "units": "K/uL", "reference_range": "4.0-11.0", "status": "normal"},
                        "hemoglobin": {"value": 12.8, "units": "g/dL", "reference_range": "12.0-16.0", "status": "normal"},
                        "platelets": {"value": 285, "units": "K/uL", "reference_range": "150-450", "status": "normal"}
                    },
                    "interpretation": "Normal complete blood count"
                },
                {
                    "test_name": "Basic Metabolic Panel",
                    "collection_date": "2024-10-11T06:00:00Z",
                    "resulted_date": "2024-10-11T07:45:00Z",
                    "results": {
                        "glucose": {"value": 145, "units": "mg/dL", "reference_range": "70-100", "status": "high"},
                        "creatinine": {"value": 1.1, "units": "mg/dL", "reference_range": "0.7-1.3", "status": "normal"},
                        "sodium": {"value": 138, "units": "mEq/L", "reference_range": "136-145", "status": "normal"}
                    },
                    "interpretation": "Mild hyperglycemia, otherwise normal"
                }
            ],
            "critical_values": [],
            "trending_data": {
                "glucose_trend": "stable_elevated",
                "kidney_function": "stable",
                "inflammatory_markers": "improving"
            },
            "pending_results": [
                {"test_name": "Blood Culture", "expected_result_time": "2024-10-12T06:00:00Z"}
            ]
        }
    },

    "vitals_monitoring_system": {
        "name": "Vitals Monitoring System Access",
        "description": "Access patient monitoring systems for real-time and historical vital signs data",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "monitoring_type": {"type": "string", "description": "Type of monitoring", "enum": ["continuous", "spot_check", "trending", "all"]},
            "time_window": {"type": "string", "description": "Time window for vital signs data"},
            "include_alerts": {"type": "boolean", "description": "Include clinical alerts and alarms"}
        },
        "mock_response": {
            "patient_id": "PAT789012",
            "monitoring_status": "continuous",
            "current_vitals": {
                "blood_pressure": {
                    "systolic": 126,
                    "diastolic": 78,
                    "mean_arterial_pressure": 94,
                    "timestamp": "2024-10-11T10:30:00Z",
                    "method": "automated_cuff"
                },
                "heart_rate": {
                    "rate": 74,
                    "rhythm": "sinus_rhythm",
                    "quality": "good",
                    "timestamp": "2024-10-11T10:30:00Z"
                },
                "respiratory_rate": {
                    "rate": 16,
                    "pattern": "regular",
                    "effort": "unlabored",
                    "timestamp": "2024-10-11T10:30:00Z"
                },
                "oxygen_saturation": {
                    "spo2": 98,
                    "oxygen_delivery": "room_air",
                    "perfusion_index": 2.1,
                    "timestamp": "2024-10-11T10:30:00Z"
                },
                "temperature": {
                    "value": 98.4,
                    "route": "oral",
                    "timestamp": "2024-10-11T10:30:00Z"
                }
            },
            "vital_trends": {
                "blood_pressure_trend": "stable",
                "heart_rate_variability": "normal",
                "respiratory_pattern": "stable",
                "temperature_trend": "afebrile"
            },
            "alerts": [],
            "clinical_assessment": {
                "hemodynamic_stability": "stable",
                "respiratory_status": "adequate",
                "neurological_status": "alert_oriented",
                "overall_acuity": "low"
            }
        }
    },

    "medical_necessity_engine": {
        "name": "Medical Necessity Assessment Engine",
        "description": "Advanced clinical decision support engine for medical necessity determination and level of care assessment",
        "input_schema": {
            "patient_data": {"type": "object", "description": "Comprehensive patient clinical data"},
            "assessment_type": {"type": "string", "description": "Type of assessment", "enum": ["admission", "continued_stay", "discharge_planning"]},
            "clinical_criteria": {"type": "string", "description": "Clinical criteria set to apply"},
            "payer_guidelines": {"type": "string", "description": "Specific payer guidelines"}
        },
        "mock_response": {
            "assessment_id": "MN_20241011_001",
            "patient_id": "PAT789012",
            "assessment_type": "continued_stay",
            "medical_necessity_score": 0.68,
            "recommendation": "discharge_planning_appropriate",
            "level_of_care_analysis": {
                "current_level": "acute_inpatient",
                "appropriate_level": "skilled_nursing_facility",
                "rationale": "Patient clinically stable, ambulating, no longer requires acute level monitoring",
                "alternative_settings": [
                    {"setting": "skilled_nursing_facility", "appropriateness": 0.92},
                    {"setting": "home_health", "appropriateness": 0.76},
                    {"setting": "outpatient_follow_up", "appropriateness": 0.84}
                ]
            },
            "clinical_indicators": {
                "stability_indicators": [
                    {"indicator": "vital_signs_stable", "status": True, "weight": 0.3},
                    {"indicator": "laboratory_values_stable", "status": True, "weight": 0.2},
                    {"indicator": "no_acute_deterioration", "status": True, "weight": 0.4}
                ],
                "functional_status": {
                    "mobility": "ambulatory_with_assistance",
                    "activities_of_daily_living": "modified_independent",
                    "cognitive_status": "alert_oriented"
                },
                "discharge_barriers": [
                    {"barrier": "placement_coordination", "severity": "moderate", "estimated_resolution": "24-48_hours"}
                ]
            },
            "cost_benefit_analysis": {
                "current_daily_cost": 2340.50,
                "alternative_setting_cost": 485.75,
                "potential_daily_savings": 1854.75,
                "quality_impact": "maintained_or_improved"
            }
        }
    },

    "healthcare_data_exchange": {
        "name": "Healthcare Data Exchange Platform",
        "description": "Healthcare interoperability platform for accessing multi-source clinical data and care coordination",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "data_sources": {"type": "array", "description": "Healthcare data sources to query"},
            "exchange_networks": {"type": "array", "description": "HIE networks to access"},
            "care_coordination_scope": {"type": "string", "description": "Scope of care coordination data"}
        },
        "mock_response": {
            "patient_id": "PAT789012",
            "exchange_query_id": "HIE_20241011_001",
            "participating_organizations": [
                {
                    "organization": "Metro Regional Medical Center",
                    "network": "CommonWell",
                    "data_available": ["encounters", "medications", "allergies", "lab_results"],
                    "last_encounter": "2024-10-05"
                },
                {
                    "organization": "Community Health Partners",
                    "network": "Carequality",
                    "data_available": ["primary_care_visits", "immunizations", "care_plans"],
                    "last_encounter": "2024-09-15"
                }
            ],
            "care_coordination_data": {
                "care_transitions": [
                    {
                        "transition_date": "2024-10-05",
                        "from_setting": "emergency_department",
                        "to_setting": "inpatient_acute_care",
                        "transition_reason": "admission_for_pneumonia",
                        "care_team_communication": "complete"
                    }
                ],
                "care_gaps": [
                    {
                        "gap_type": "preventive_care",
                        "description": "Mammography screening overdue",
                        "priority": "medium",
                        "due_date": "2024-08-15"
                    }
                ],
                "medication_reconciliation": {
                    "discrepancies_found": 1,
                    "home_medications": 8,
                    "hospital_medications": 6,
                    "discontinued_medications": 2,
                    "new_medications": 1
                }
            },
            "quality_metrics": {
                "data_completeness": 0.91,
                "data_freshness": 0.88,
                "interoperability_score": 0.94
            }
        }
    },

    # Utilization Management - Appeals Processing Tools
    "appeal_letters_api": {
        "name": "Appeal Letters API Access",
        "description": "Access member and provider appeal letters from appeals management systems",
        "input_schema": {
            "appeal_id": {"type": "string", "description": "Appeal identifier"},
            "member_id": {"type": "string", "description": "Member identifier (optional)"},
            "appeal_type": {"type": "string", "description": "Type of appeal", "enum": ["medical_pa", "pharmacy_pa", "claim_denial", "coverage_determination"]},
            "include_attachments": {"type": "boolean", "description": "Include supporting documentation"}
        },
        "mock_response": {
            "appeal_id": "APP_20241011_001",
            "member_id": "MEM123456",
            "appeal_type": "medical_pa",
            "submission_details": {
                "submission_date": "2024-10-11T09:00:00Z",
                "submission_method": "online_portal",
                "submitter_type": "member",
                "urgency_level": "standard"
            },
            "appeal_content": {
                "primary_letter": {
                    "content": "I am writing to appeal the denial of my MRI scan of the lumbar spine. My physician Dr. Smith has recommended this imaging due to persistent lower back pain that has not responded to 6 weeks of conservative treatment including physical therapy and medication. The pain is affecting my ability to work and perform daily activities. I believe this scan is medically necessary to determine the cause of my ongoing symptoms and guide appropriate treatment.",
                    "word_count": 67,
                    "language": "English",
                    "sentiment": "formal_concerned"
                },
                "supporting_arguments": [
                    "Failed conservative treatment for 6 weeks",
                    "Physician recommendation for imaging",
                    "Impact on daily functioning and work",
                    "Medical necessity for diagnosis and treatment planning"
                ],
                "clinical_references": [
                    "Dr. Smith's referral letter dated 2024-09-15",
                    "Physical therapy progress notes",
                    "Medication trial documentation"
                ]
            },
            "attachments": [
                {
                    "attachment_id": "ATT_001",
                    "type": "physician_letter",
                    "description": "Dr. Smith's clinical justification letter",
                    "date": "2024-09-15"
                },
                {
                    "attachment_id": "ATT_002",
                    "type": "treatment_records",
                    "description": "Physical therapy progress notes",
                    "date": "2024-09-01"
                }
            ],
            "processing_status": {
                "current_status": "received",
                "assigned_reviewer": "Review Team A",
                "target_completion_date": "2024-10-25",
                "priority_level": "standard"
            }
        }
    },

    "denial_reasons_database": {
        "name": "Denial Reasons Database Access",
        "description": "Access original denial reasons and decision documentation for linkage analysis",
        "input_schema": {
            "denial_id": {"type": "string", "description": "Original denial identifier"},
            "member_id": {"type": "string", "description": "Member identifier"},
            "service_type": {"type": "string", "description": "Type of denied service"},
            "denial_date_range": {"type": "string", "description": "Date range for denial search"}
        },
        "mock_response": {
            "denial_id": "DENY_20241001_001",
            "member_id": "MEM123456",
            "denial_details": {
                "denial_date": "2024-10-01T14:30:00Z",
                "service_denied": "MRI Lumbar Spine without contrast",
                "service_code": "72148",
                "requesting_provider": "Dr. Smith, MD",
                "denial_category": "medical_necessity"
            },
            "denial_reasoning": {
                "primary_reason": "Insufficient documentation of medical necessity",
                "secondary_reasons": [
                    "Conservative treatment duration not adequately documented",
                    "Clinical indication not clearly established"
                ],
                "clinical_criteria_not_met": [
                    "6 weeks of documented conservative treatment",
                    "Red flag symptoms requiring urgent imaging",
                    "Neurological deficits documented"
                ],
                "policy_references": [
                    "Medical Policy MP-IMG-001: Lumbar Spine MRI Coverage Criteria",
                    "Clinical Guidelines CG-MSK-003: Conservative Treatment Requirements"
                ]
            },
            "review_details": {
                "reviewing_physician": "Dr. Johnson, MD",
                "review_date": "2024-10-01T14:30:00Z",
                "review_type": "clinical_review",
                "peer_review_required": False,
                "decision_confidence": 0.87
            },
            "denial_codes": [
                {"code": "MN001", "description": "Medical necessity not established"},
                {"code": "CT002", "description": "Conservative treatment requirements not met"}
            ],
            "member_notification": {
                "notification_date": "2024-10-01T16:00:00Z",
                "notification_method": "mail_and_portal",
                "appeal_deadline": "2024-11-01",
                "appeal_instructions_provided": True
            }
        }
    },

    "policies_database": {
        "name": "Policies Database Access",
        "description": "Access comprehensive healthcare policies and guidelines for relevant policy identification and matching",
        "input_schema": {
            "service_code": {"type": "string", "description": "Medical service or procedure code"},
            "policy_category": {"type": "string", "description": "Policy category", "enum": ["medical", "pharmacy", "coverage", "clinical"]},
            "search_terms": {"type": "array", "description": "Keywords for policy search"},
            "include_archived": {"type": "boolean", "description": "Include archived policies"}
        },
        "mock_response": {
            "search_query": "MRI lumbar spine medical necessity",
            "policies_found": 3,
            "relevant_policies": [
                {
                    "policy_id": "MP-IMG-001",
                    "policy_title": "Lumbar Spine MRI Coverage Criteria",
                    "version": "2024.2",
                    "effective_date": "2024-07-01",
                    "policy_type": "medical_necessity",
                    "relevance_score": 0.96,
                    "coverage_criteria": {
                        "covered_indications": [
                            "Red flag symptoms (fever, neurological deficits, bowel/bladder dysfunction)",
                            "Failed conservative treatment for 6+ weeks",
                            "Persistent or worsening symptoms despite appropriate treatment",
                            "Suspected serious underlying pathology"
                        ],
                        "documentation_requirements": [
                            "Clinical history and physical examination findings",
                            "Documentation of conservative treatment trials",
                            "Symptom severity and functional impact assessment",
                            "Provider clinical justification"
                        ],
                        "exclusions": [
                            "Routine screening without clinical indication",
                            "Imaging for chronic stable conditions without change",
                            "Repeat imaging without clinical progression"
                        ]
                    }
                },
                {
                    "policy_id": "CG-MSK-003",
                    "policy_title": "Musculoskeletal Conservative Treatment Requirements",
                    "version": "2024.1",
                    "effective_date": "2024-06-15",
                    "policy_type": "clinical_guideline",
                    "relevance_score": 0.89,
                    "treatment_requirements": {
                        "first_line_treatments": [
                            "NSAIDs or acetaminophen for pain management",
                            "Activity modification and ergonomic assessment",
                            "Physical therapy evaluation and treatment"
                        ],
                        "duration_requirements": {
                            "minimum_conservative_trial": "6_weeks",
                            "documentation_frequency": "weekly_progress_notes",
                            "outcome_measures": "pain_scales_functional_assessment"
                        }
                    }
                }
            ],
            "policy_updates": {
                "recent_changes": [
                    {
                        "policy_id": "MP-IMG-001",
                        "change_date": "2024-07-01",
                        "change_description": "Updated conservative treatment duration from 4 to 6 weeks"
                    }
                ],
                "upcoming_changes": []
            }
        }
    },

    "evidence_database": {
        "name": "Referenced Evidence Database",
        "description": "Access clinical evidence and supporting documentation for comprehensive analysis",
        "input_schema": {
            "evidence_type": {"type": "string", "description": "Type of evidence", "enum": ["clinical_studies", "guidelines", "protocols", "literature"]},
            "medical_condition": {"type": "string", "description": "Medical condition or clinical topic"},
            "search_terms": {"type": "array", "description": "Evidence search terms"},
            "evidence_level": {"type": "string", "description": "Level of evidence", "enum": ["systematic_review", "rct", "cohort", "case_series", "expert_opinion"]}
        },
        "mock_response": {
            "search_query": "lumbar spine MRI diagnostic accuracy low back pain",
            "evidence_results": [
                {
                    "evidence_id": "EV_20241011_001",
                    "title": "Diagnostic Accuracy of MRI for Lumbar Spine Pathology in Chronic Low Back Pain",
                    "source": "Journal of Spine Medicine",
                    "publication_date": "2024-08-15",
                    "evidence_level": "systematic_review",
                    "relevance_score": 0.94,
                    "key_findings": [
                        "MRI sensitivity 87% for disc herniation detection",
                        "Specificity 92% for nerve root compression",
                        "Clinical correlation essential for treatment planning",
                        "Conservative treatment trial recommended before imaging"
                    ],
                    "clinical_implications": "MRI most beneficial after failed conservative treatment to guide surgical planning"
                },
                {
                    "evidence_id": "EV_20241011_002",
                    "title": "Conservative Treatment Effectiveness in Acute Low Back Pain",
                    "source": "Physical Medicine & Rehabilitation Journal",
                    "publication_date": "2024-06-20",
                    "evidence_level": "rct",
                    "relevance_score": 0.88,
                    "key_findings": [
                        "Physical therapy effective in 68% of patients within 6 weeks",
                        "Combined therapy (PT + medication) superior to single modality",
                        "Early imaging not associated with improved outcomes",
                        "Patient education improves treatment adherence"
                    ],
                    "clinical_implications": "Six-week conservative trial is evidence-based standard of care"
                }
            ],
            "clinical_guidelines": [
                {
                    "guideline_id": "GL_SPINE_001",
                    "organization": "American College of Radiology",
                    "title": "ACR Appropriateness Criteria for Low Back Pain",
                    "recommendation_strength": "strong",
                    "relevant_recommendations": [
                        "Conservative treatment trial of 6+ weeks before imaging",
                        "MRI appropriate for persistent symptoms after conservative care",
                        "Clinical correlation required for imaging interpretation"
                    ]
                }
            ],
            "evidence_quality": {
                "overall_strength": "high",
                "consistency_across_studies": 0.91,
                "clinical_applicability": 0.94,
                "recency_score": 0.89
            }
        }
    },

    "healthcare_appeals_nlp": {
        "name": "Healthcare Appeals NLP Processing Engine",
        "description": "Advanced NLP engine specialized for healthcare appeals processing and medical terminology analysis",
        "input_schema": {
            "appeal_text": {"type": "string", "description": "Appeal letter text content"},
            "processing_mode": {"type": "string", "description": "Processing mode", "enum": ["summarization", "argument_extraction", "sentiment_analysis", "comprehensive"]},
            "medical_domain": {"type": "string", "description": "Medical domain focus"},
            "output_length": {"type": "string", "description": "Desired output length", "enum": ["brief", "standard", "detailed"]}
        },
        "mock_response": {
            "processing_id": "NLP_APP_20241011_001",
            "appeal_id": "APP_20241011_001",
            "text_analysis": {
                "word_count": 247,
                "reading_level": "12th_grade",
                "sentiment_score": 0.72,
                "urgency_indicators": ["persistent_pain", "affecting_work", "daily_activities"],
                "medical_terminology_density": 0.34
            },
            "key_arguments_extracted": [
                {
                    "argument": "Failed conservative treatment",
                    "supporting_evidence": "6 weeks of physical therapy and medication",
                    "strength": 0.89,
                    "medical_relevance": 0.94
                },
                {
                    "argument": "Physician recommendation",
                    "supporting_evidence": "Dr. Smith has recommended this imaging",
                    "strength": 0.87,
                    "medical_relevance": 0.91
                },
                {
                    "argument": "Functional impact",
                    "supporting_evidence": "affecting my ability to work and perform daily activities",
                    "strength": 0.83,
                    "medical_relevance": 0.78
                }
            ],
            "medical_entities": [
                {"entity": "MRI lumbar spine", "type": "procedure", "confidence": 0.98},
                {"entity": "lower back pain", "type": "symptom", "confidence": 0.96},
                {"entity": "physical therapy", "type": "treatment", "confidence": 0.94},
                {"entity": "Dr. Smith", "type": "provider", "confidence": 0.92}
            ],
            "summary": {
                "executive_summary": "Member appeals denial of lumbar spine MRI, citing 6 weeks of failed conservative treatment including physical therapy and medication. Physician has recommended imaging for persistent pain affecting work and daily activities.",
                "key_points": [
                    "Conservative treatment trial completed",
                    "Physician support for imaging request",
                    "Documented functional impairment",
                    "Seeking diagnostic clarification"
                ],
                "clinical_context": "Chronic low back pain with failed conservative management"
            }
        }
    },

    "intelligent_linking_engine": {
        "name": "Intelligent Linking Engine",
        "description": "Machine learning engine for intelligent linking between appeals, denials, policies, and evidence",
        "input_schema": {
            "source_content": {"type": "string", "description": "Source content for linking analysis"},
            "target_databases": {"type": "array", "description": "Target databases to link against"},
            "linking_algorithms": {"type": "array", "description": "Linking algorithms to apply"},
            "confidence_threshold": {"type": "float", "description": "Minimum confidence for automated linking"}
        },
        "mock_response": {
            "linking_session_id": "LINK_20241011_001",
            "source_document_id": "APP_20241011_001",
            "linking_results": {
                "denial_linkages": [
                    {
                        "denial_id": "DENY_20241001_001",
                        "confidence_score": 0.96,
                        "match_factors": [
                            {"factor": "member_id_match", "weight": 0.3, "score": 1.0},
                            {"factor": "service_code_match", "weight": 0.25, "score": 1.0},
                            {"factor": "temporal_proximity", "weight": 0.2, "score": 0.91},
                            {"factor": "clinical_context_similarity", "weight": 0.25, "score": 0.94}
                        ],
                        "linkage_rationale": "Perfect match on member ID and service code with high clinical similarity"
                    }
                ],
                "policy_linkages": [
                    {
                        "policy_id": "MP-IMG-001",
                        "policy_title": "Lumbar Spine MRI Coverage Criteria",
                        "confidence_score": 0.93,
                        "relevance_factors": [
                            {"factor": "service_type_match", "score": 1.0},
                            {"factor": "clinical_criteria_alignment", "score": 0.89},
                            {"factor": "coverage_context_match", "score": 0.91}
                        ],
                        "applicable_criteria": [
                            "Conservative treatment requirements",
                            "Medical necessity documentation",
                            "Clinical indication standards"
                        ]
                    },
                    {
                        "policy_id": "CG-MSK-003",
                        "policy_title": "Conservative Treatment Requirements",
                        "confidence_score": 0.87,
                        "relevance_factors": [
                            {"factor": "treatment_pathway_match", "score": 0.94},
                            {"factor": "duration_requirements_match", "score": 0.83}
                        ]
                    }
                ],
                "evidence_linkages": [
                    {
                        "evidence_id": "EV_20241011_001",
                        "title": "Diagnostic Accuracy of MRI for Lumbar Spine Pathology",
                        "confidence_score": 0.89,
                        "relevance_type": "diagnostic_utility",
                        "supporting_points": [
                            "Validates clinical appropriateness of requested imaging",
                            "Supports medical necessity argument",
                            "Demonstrates evidence-based practice"
                        ]
                    }
                ]
            },
            "linking_quality_metrics": {
                "overall_confidence": 0.92,
                "cross_reference_completeness": 0.94,
                "temporal_consistency": 0.96,
                "clinical_coherence": 0.91
            },
            "automated_summary": {
                "primary_connections": "Appeal directly relates to denial DENY_20241001_001 for same service and member",
                "policy_alignment": "Appeal arguments align with MP-IMG-001 coverage criteria requirements",
                "evidence_support": "Clinical evidence supports appropriateness of requested imaging after conservative treatment"
            }
        }
    },

    # Additional Eligibility Verification Tools
    "eligibility_benefit_summary": {
        "name": "Eligibility Benefit Summary",
        "description": "Comprehensive benefit summary with detailed coverage information and financial details",
        "input_schema": {
            "member_id": {"type": "string", "description": "Insurance member ID"},
            "plan_year": {"type": "string", "description": "Plan year (e.g., '2024')"},
            "benefit_category": {"type": "string", "description": "Specific benefit category", "enum": ["all", "medical", "pharmacy", "dental", "vision"]}
        },
        "mock_response": {
            "member_id": "BEN456789",
            "plan_summary": {
                "plan_name": "Health Plus Premium",
                "plan_year": "2024",
                "network_type": "HMO",
                "formulary_tier": "Preferred"
            },
            "financial_summary": {
                "deductible_individual": "$1500",
                "deductible_family": "$3000",
                "deductible_met": "$750",
                "out_of_pocket_max": "$5000",
                "out_of_pocket_met": "$1800"
            },
            "benefit_details": {
                "preventive_care": {"coverage": "100%", "copay": "$0", "notes": "In-network only"},
                "primary_care": {"coverage": "90%", "copay": "$25"},
                "specialist_care": {"coverage": "80%", "copay": "$50", "referral_required": True},
                "emergency_services": {"coverage": "80%", "copay": "$200"},
                "prescription_drugs": {
                    "generic": "$10",
                    "brand_preferred": "$35",
                    "brand_non_preferred": "$70",
                    "specialty": "25% coinsurance"
                }
            },
            "annual_limits": {
                "physical_therapy": "20 visits",
                "mental_health": "Unlimited",
                "chiropractic": "12 visits"
            }
        }
    },

    "eligibility_network_provider_search": {
        "name": "Network Provider Search",
        "description": "Search for in-network healthcare providers by specialty, location, and availability",
        "input_schema": {
            "member_id": {"type": "string", "description": "Insurance member ID"},
            "specialty": {"type": "string", "description": "Provider specialty (e.g., 'cardiology', 'dermatology')"},
            "location": {"type": "string", "description": "Location (city, state, or zip code)"},
            "radius_miles": {"type": "integer", "description": "Search radius in miles", "default": 25}
        },
        "mock_response": {
            "search_criteria": {
                "specialty": "cardiology",
                "location": "Seattle, WA",
                "radius": 25
            },
            "total_providers": 34,
            "providers": [
                {
                    "npi": "1234567890",
                    "name": "Dr. Sarah Johnson, MD",
                    "specialty": "Cardiology",
                    "practice_name": "Seattle Heart Institute",
                    "address": "1234 Medical Center Dr, Seattle, WA 98101",
                    "phone": "206-555-HEART",
                    "distance_miles": 3.2,
                    "accepting_new_patients": True,
                    "next_available": "2024-02-15",
                    "network_tier": "Preferred",
                    "quality_rating": 4.8,
                    "board_certifications": ["Cardiovascular Disease", "Internal Medicine"]
                },
                {
                    "npi": "2345678901",
                    "name": "Dr. Michael Chen, MD",
                    "specialty": "Interventional Cardiology",
                    "practice_name": "Northwest Cardiac Associates",
                    "address": "5678 Health Way, Bellevue, WA 98004",
                    "phone": "425-555-CARD",
                    "distance_miles": 8.7,
                    "accepting_new_patients": True,
                    "next_available": "2024-02-20",
                    "network_tier": "Standard",
                    "quality_rating": 4.6,
                    "board_certifications": ["Interventional Cardiology", "Cardiovascular Disease"]
                }
            ],
            "search_metadata": {
                "search_timestamp": "2024-01-16T10:30:00Z",
                "results_cached_until": "2024-01-16T11:30:00Z",
                "provider_data_last_updated": "2024-01-15"
            }
        }
    },

    "eligibility_prior_authorization_check": {
        "name": "Prior Authorization Check",
        "description": "Check prior authorization requirements for specific medical services and procedures",
        "input_schema": {
            "member_id": {"type": "string", "description": "Insurance member ID"},
            "service_codes": {"type": "array", "description": "CPT/HCPCS codes for services"},
            "provider_npi": {"type": "string", "description": "Provider NPI number"},
            "service_date": {"type": "string", "description": "Planned service date (YYYY-MM-DD)"}
        },
        "mock_response": {
            "member_id": "PA789012",
            "prior_auth_summary": {
                "total_services": 3,
                "requiring_auth": 2,
                "pre_approved": 0,
                "not_required": 1
            },
            "service_details": [
                {
                    "service_code": "77078",
                    "service_name": "Computed tomographic bone density study",
                    "auth_required": True,
                    "auth_status": "Required - Not Submitted",
                    "estimated_approval_time": "3-5 business days",
                    "submission_method": "Online portal or fax",
                    "required_documentation": [
                        "Clinical notes justifying medical necessity",
                        "Previous imaging reports",
                        "Treatment history"
                    ]
                },
                {
                    "service_code": "99213",
                    "service_name": "Office visit, established patient",
                    "auth_required": False,
                    "auth_status": "Not Required",
                    "notes": "Routine office visits do not require prior authorization"
                },
                {
                    "service_code": "73721",
                    "service_name": "MRI lower extremity, without contrast",
                    "auth_required": True,
                    "auth_status": "Required - Not Submitted",
                    "estimated_approval_time": "5-7 business days",
                    "submission_method": "Online portal",
                    "clinical_criteria": [
                        "Conservative treatment attempted for 6+ weeks",
                        "Persistent symptoms affecting function",
                        "Clinical exam findings consistent with pathology"
                    ]
                }
            ],
            "contact_information": {
                "prior_auth_phone": "1-800-555-AUTH",
                "online_portal": "https://provider.healthplan.com/auth",
                "fax_number": "1-800-555-FAX",
                "hours": "Monday-Friday 8AM-6PM EST"
            }
        }
    },

    "eligibility_cost_estimate": {
        "name": "Medical Cost Estimate",
        "description": "Calculate estimated patient costs for medical services based on current benefits",
        "input_schema": {
            "member_id": {"type": "string", "description": "Insurance member ID"},
            "service_codes": {"type": "array", "description": "CPT codes for services"},
            "provider_npi": {"type": "string", "description": "Provider NPI number"},
            "facility_type": {"type": "string", "description": "Facility type", "enum": ["office", "hospital_outpatient", "hospital_inpatient", "ambulatory_surgery"]}
        },
        "mock_response": {
            "member_id": "COST123456",
            "estimate_date": "2024-01-16",
            "total_estimate": {
                "provider_charges": "$2,850",
                "allowed_amount": "$2,200",
                "patient_responsibility": "$340",
                "insurance_payment": "$1,860"
            },
            "service_breakdown": [
                {
                    "service_code": "99214",
                    "description": "Office visit, detailed",
                    "provider_charge": "$350",
                    "allowed_amount": "$280",
                    "patient_copay": "$50",
                    "deductible_applied": "$0",
                    "coinsurance": "$46",
                    "patient_total": "$96",
                    "insurance_pays": "$184"
                },
                {
                    "service_code": "93306",
                    "description": "Echocardiography, complete",
                    "provider_charge": "$2,500",
                    "allowed_amount": "$1,920",
                    "patient_copay": "$0",
                    "deductible_applied": "$200",
                    "coinsurance": "$344",
                    "patient_total": "$544",
                    "insurance_pays": "$1,376"
                }
            ],
            "benefit_application": {
                "deductible_remaining_before": "$750",
                "deductible_remaining_after": "$550",
                "out_of_pocket_remaining": "$3,200",
                "annual_benefit_usage": "35%"
            },
            "estimate_accuracy": {
                "confidence_level": "high",
                "factors_affecting_cost": [
                    "Actual charges may vary by provider",
                    "Additional services may be required",
                    "Benefit changes during plan year"
                ],
                "valid_through": "2024-02-16"
            }
        }
    },

    # Appeals & Grievances Case Management Tools
    "case_management_database": {
        "name": "Case Management Database",
        "description": "HIPAA-compliant database connector for case management, member information, and historical case data",
        "input_schema": {
            "query_type": {"type": "string", "description": "Type of query to execute", "enum": ["member_lookup", "case_history", "similar_cases", "update_status"]},
            "member_id": {"type": "string", "description": "Member identifier for data retrieval"},
            "case_id": {"type": "string", "description": "Case identifier for specific case operations"},
            "search_criteria": {"type": "object", "description": "Additional search parameters"}
        },
        "mock_response": {
            "query_id": "QRY_20241017_001",
            "member_info": {
                "member_id": "MEM987654321",
                "plan_type": "medicare_advantage",
                "enrollment_date": "2023-01-01",
                "status": "active",
                "demographics": {
                    "age_range": "65-70",
                    "state": "CA",
                    "zip_code": "90210"
                }
            },
            "case_history": [
                {
                    "case_id": "CASE_20240801_001",
                    "case_type": "medical_appeal",
                    "status": "approved",
                    "resolution_date": "2024-08-15",
                    "category": "diagnostic_imaging",
                    "outcome": "approved_with_conditions"
                },
                {
                    "case_id": "CASE_20240301_002",
                    "case_type": "pharmacy_appeal",
                    "status": "denied",
                    "resolution_date": "2024-03-20",
                    "category": "formulary_exception",
                    "outcome": "alternative_medication_approved"
                }
            ],
            "similar_cases": [
                {
                    "case_id": "CASE_20240915_003",
                    "similarity_score": 0.87,
                    "category": "diagnostic_imaging",
                    "resolution": "approved",
                    "processing_days": 12
                }
            ],
            "compliance_flags": [],
            "processing_time_ms": 245,
            "hipaa_audit_id": "AUDIT_20241017_001"
        }
    },

    "healthcare_appeals_nlp_classifier": {
        "name": "Healthcare Appeals NLP Classifier",
        "description": "Advanced NLP engine for healthcare appeals and grievances text analysis with medical terminology understanding",
        "input_schema": {
            "case_content": {"type": "string", "description": "Full text content of the appeal or grievance"},
            "analysis_type": {"type": "string", "description": "Type of analysis to perform", "enum": ["classification", "urgency_assessment", "clinical_extraction", "sentiment_analysis"]},
            "context_data": {"type": "object", "description": "Additional context like member plan type, submission method"},
            "confidence_threshold": {"type": "number", "description": "Minimum confidence threshold for classifications (0.0-1.0)"}
        },
        "mock_response": {
            "analysis_id": "NLP_20241017_001",
            "text_analysis": {
                "primary_category": {
                    "category": "medical_appeal",
                    "subcategory": "diagnostic_imaging",
                    "confidence": 0.92,
                    "keywords": ["MRI", "lower back pain", "conservative treatment", "medical necessity"]
                },
                "urgency_indicators": {
                    "urgency_level": "standard_urgent",
                    "confidence": 0.89,
                    "indicators": ["persistent pain", "failed treatment", "physician recommendation"],
                    "escalation_triggers": []
                },
                "clinical_entities": {
                    "conditions": [
                        {"name": "chronic lower back pain", "code": "M54.5", "confidence": 0.94},
                        {"name": "radiculopathy", "code": "M54.1", "confidence": 0.76}
                    ],
                    "procedures": [
                        {"name": "MRI lumbar spine", "code": "72148", "confidence": 0.98}
                    ],
                    "medications": [
                        {"name": "ibuprofen", "generic": "ibuprofen", "confidence": 0.85}
                    ],
                    "treatments": [
                        {"name": "physical therapy", "code": "97110", "confidence": 0.91}
                    ]
                },
                "sentiment_analysis": {
                    "overall_sentiment": "frustrated_but_polite",
                    "urgency_tone": "moderate",
                    "compliance_indicators": ["provided documentation", "followed prior steps"]
                },
                "regulatory_keywords": {
                    "cms_references": ["medical necessity", "appeal rights"],
                    "timeline_mentions": ["30 days", "expedited review"],
                    "compliance_terms": ["prior authorization", "coverage determination"]
                }
            },
            "processing_metadata": {
                "processing_time_ms": 1567,
                "model_version": "healthcare_nlp_v2.1",
                "language_detected": "en_US",
                "text_quality_score": 0.94,
                "medical_terminology_density": 0.67
            }
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
        mock_tools = await self._generate_mock_tools_from_component_config()

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
