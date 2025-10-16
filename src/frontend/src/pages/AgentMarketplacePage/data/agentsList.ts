import type { AgentSpecItem } from "@/controllers/API/queries/agent-marketplace/use-get-agent-marketplace";

type StaticAgentInput = {
  name: string;
  description: string;
  tag: string;
  version?: string;
  flow_id?: string;
};

const RAW_AGENTS_LIST: StaticAgentInput[] = [
  {
    name: "Appointment Concierge Agent",
    description:
      "Automates appointment scheduling using EHR calendars, insurance eligibility, and preferred location. Sends reminders and follow-ups across SMS and email.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Post-Visit Q&A Agent",
    description:
      "Uses discharge summaries, physician notes, and medication records to answer patient questions after a visit, supporting better adherence and satisfaction.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Virtual Health Navigator Agent",
    description:
      "Uses symptom checkers, claims history, and plan rules to guide patients to correct care setting or provider using interactive chatbot interface.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Insurance Benefits Explainer Agent",
    description:
      "Reads benefits summaries, EOBs, and plan documents to explain deductibles, coinsurance, and covered services to members via chatbot or portal.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Patient Feedback Analyzer Agent",
    description:
      "Analyzes call center logs, survey responses, and complaints to extract themes and sentiment. Helps improve member experience metrics.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Medication Adherence Coach Agent",
    description:
      "Uses pharmacy claims, care plans, and refill history to send targeted reminders and offer educational content for non-adherence.",
    tag: "Patient Experience",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Clinical Documentation Scribe Agent",
    description:
      "Converts real-time audio transcripts or visit recordings into structured clinical notes. Integrates with EHR and uses transcription + NLP.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Medical Coding Assistant Agent",
    description:
      "Uses diagnosis descriptions, procedure notes, and coding libraries (ICD, CPT) to suggest accurate codes. Highlights supporting evidence.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Clinical Order Advisor Agent",
    description:
      "Uses EHR, labs, diagnosis codes, and care guidelines to suggest appropriate tests, referrals, or therapies to providers at point of care.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Onboarding Q&A Agent",
    description:
      "Provides step-by-step instructions for onboarding, using policy manuals, SOPs, and HR data. Responds to questions via natural language interface.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Care Coordination Summarizer Agent",
    description:
      "Gathers structured and unstructured data from multiple providers to generate referral packets and discharge summaries for transitions of care.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Compliance Documentation Check Agent",
    description:
      "Audits provider notes for regulatory compliance using documentation standards, prior audits, and template matching. Flags missing attestation elements.",
    tag: "Provider Enablement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Inpatient Utilization Monitor Agent",
    description:
      "Analyzes inpatient records, vitals, and lab results to identify cases no longer meeting medical necessity. Supports level of care reviews.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Appeals Summarization Agent",
    description:
      "Summarizes member or provider appeal letters using NLP, linking to the original denial reason, policy, and referenced evidence.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Network Alternative Suggestion Agent",
    description:
      "Matches PA request against formulary, network, and eligibility to suggest lower-cost, in-network, or guideline-supported alternatives.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Utilization Management Intake Triage Agent",
    description:
      "Sorts PA requests by clinical complexity, urgency, and benefit type. Uses PA form content, eligibility, and historical approvals.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Utilization Management Review Prep Agent",
    description:
      "Gathers all supporting documentation including clinical notes, prior denials, and criteria for physician reviewer prep packets.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Additional Info Request Agent",
    description:
      "Detects missing data fields in PA or Utilization Management forms and generates structured, compliant info request letters for providers.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Risk Stratification Agent",
    description:
      "Combines claims, SDoH, and EHR data to score and prioritize patients for care management outreach or chronic care programs.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "SDoH Needs Identifier Agent",
    description:
      "Scans assessments, intake notes, and case manager comments to identify food insecurity, housing instability, or other social needs.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Readmission Risk Predictor Agent",
    description:
      "Uses post-discharge data, prior utilization, and comorbidity indexes to predict 30-day readmission risks and flag high-risk patients.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Care Plan Compliance Tracker Agent",
    description:
      "Monitors appointment attendance, lab results, and prescription fills to detect care plan deviations. Sends alerts to care teams.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Multi-Provider Coordination Agent",
    description:
      "Aggregates referrals, labs, notes, and patient messages across providers. Builds longitudinal care view to coordinate interventions.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Patient Progress Summarizer Agent",
    description:
      "Pulls structured outcomes and narrative documentation to summarize recent events for complex patients in care management programs.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Suspect Condition Finder Agent",
    description:
      "Uses NLP to scan clinical notes and lab data to find undocumented HCC conditions. Highlights for provider review.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Risk Coding Advisor Agent",
    description:
      "Matches encounter documentation to appropriate HCC codes. Flags gaps or annual re-documentation needs using coding rules.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Documentation Gap Filler Agent",
    description:
      "Compares submitted codes to encounter text to identify missing documentation support or missed coding opportunities.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Query Generator Agent",
    description:
      "Creates HCC coding query letters citing relevant patient notes and evidence. Ensures compliant phrasing and citations.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Code Validation Agent",
    description:
      "Validates submitted diagnoses against chart notes, labs, and procedures to avoid over-coding or audit risk.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Risk Score Optimizer Agent",
    description:
      "Simulates impact of suspected codes, non-compliant conditions, and missed RAF opportunities on risk scores across populations.",
    tag: "Risk Adjustment",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Duplicate Claim Detection Agent",
    description:
      "Uses claim line detail, NPI, DOS, and CPT patterns to flag potential duplicates or resubmissions. Prevents overpayment.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Coordination of Benefits (COB) Agent",
    description:
      "Confirms primary/secondary coverage via eligibility feeds. Flags incorrect billing sequence and adjusts claims accordingly.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "High-Cost Claim Analyzer Agent",
    description:
      "Detects atypical cost patterns using historical data, thresholds, and peer comparisons. Prioritizes high-dollar claim reviews.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Fraud and Waste Detection Agent",
    description:
      "Identifies outliers using time-series billing patterns, CPT frequency, and comparison with provider peer groups.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Claims Error Auto-Correct Agent",
    description:
      "Suggests code corrections based on denial history and rules engine. Reduces rework before payer submission.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Claims Triage Agent",
    description:
      "Segregates claims by complexity, dollar value, and clinical flags using intake fields and claims metadata.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Coverage Validation Agent",
    description:
      "Cross-checks coverage status, plan limits, and pre-auth data against each claim. Flags discrepancies and recommends actions.",
    tag: "Claims Operations",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "RFP Requirements Extraction Agent",
    description:
      "Extracts evaluation criteria, compliance requirements, and deadlines from complex RFP PDFs using layout-aware NLP and table parsing.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Proposal Drafting Assistant Agent",
    description:
      "Matches RFP questions to pre-approved language bank. Auto-generates draft responses from past submissions and content libraries.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Compliance Checklist Agent",
    description:
      "Uses document comparison to check whether response files meet every checklist item in an RFP or contract.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Contract Compliance Monitoring Agent",
    description:
      "Monitors adherence to SLAs, contract clauses, or renewal terms using performance reports and payment files.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Credentialing Assistant Agent",
    description:
      "Pulls provider license, malpractice, and work history from public sources and fills credentialing forms for payers and facilities.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Network Adequacy Analyzer Agent",
    description: "Maps provider directory and access standards against member ZIPs and time-distance rules to identify contracting needs.",
    tag: "Contracting & RFP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Member Sentiment Analyzer Agent",
    description: "Analyzes call transcripts, complaints, and feedback data to detect dissatisfaction or churn risk using sentiment analysis and call center records.",
    tag: "Member Engagement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Welcome Packet Generator Agent",
    description: "Automatically assembles personalized onboarding packets using enrollment data, eligibility, PCP assignment, and plan documents.",
    tag: "Member Engagement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Preferred Communication Channel Agent",
    description: "Uses CRM interaction data to determine and update member's preferred communication channel for outreach (SMS, phone, email, mail).",
    tag: "Member Engagement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Life Event Change Agent",
    description: "Flags qualifying life events by monitoring enrollment feeds, address changes, EDI transactions, or member updates.",
    tag: "Member Engagement",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Community Resource Match Agent",
    description: "Recommends local support services using SDoH data, zip code, assessment forms, and publicly available resource directories.",
    tag: "Population Health",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Preventive Care Gap Agent",
    description: "Detects overdue screenings using HEDIS logic and medical claims. Helps target patient outreach for compliance and care closure.",
    tag: "Population Health",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Plan Design Impact Simulator Agent",
    description: "Simulates future cost and utilization impacts of benefit changes using claims history, actuarial models, and utilization patterns.",
    tag: "Population Health",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Directory Cleaner Agent",
    description: "Compares provider directories with claims, credentialing data, and NPI registry to detect and fix outdated or inaccurate listings.",
    tag: "Provider Data Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Credential Watch Agent",
    description: "Tracks expirations and recredentialing requirements using credentialing databases, board status, and public registries.",
    tag: "Provider Data Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Taxonomy/NPI Classification Agent",
    description: "Reclassifies provider specialty using NPI taxonomy, claim patterns, and licensure data for network segmentation.",
    tag: "Provider Data Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Trend Deviation Detector Agent",
    description: "Flags anomalies in claim cost or volume trends across service lines, geographies, or populations using longitudinal claims data.",
    tag: "Actuarial / Finance",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Rate Filing Summarization Agent",
    description: "Extracts key actuarial justifications, pricing drivers, and trends from rate filings to generate summaries for internal review.",
    tag: "Actuarial / Finance",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Cost Benchmarking Agent",
    description: "Benchmarks plan costs versus Care Management, industry, and competitor data using claims, actuarial databases, and fee schedules.",
    tag: "Actuarial / Finance",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Policy Change Impact Analyzer Agent",
    description: "Summarizes Care Management/state regulation updates and maps them to impacted workflows, policies, and implementation playbooks.",
    tag: "Compliance / Audit",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Audit Response Generator Agent",
    description: "Drafts audit responses using internal logs, EHR metadata, and document retrieval. Supports Care Management, OIG, and RADV audits.",
    tag: "Compliance / Audit",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Delegated Entity Oversight Agent",
    description: "Monitors downstream entities (e.g., Utilization Management vendors) for compliance using SLAs, error reports, and audit history.",
    tag: "Compliance / Audit",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Care Management Memo Summarization Agent",
    description: "Ingests Care Management HPMS memos, filters key operational changes, and produces stakeholder alerts with summary and impact callouts.",
    tag: "Compliance / Audit",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Formulary Exception Review Agent",
    description: "Reviews exception requests using member benefit files, formulary status, clinical documentation, and pharmacy claims.",
    tag: "PBM / Pharmacy",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Specialty Drug Cost Predictor Agent",
    description: "Predicts financial impact of new or recurring specialty drugs using historical authorizations and member-level cost trends.",
    tag: "PBM / Pharmacy",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Controlled Substance Monitoring Agent",
    description: "Flags prescribing and dispensing anomalies for controlled substances using pharmacy claims, PDMP, and risk thresholds.",
    tag: "PBM / Pharmacy",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Negotiation Brief Generator",
    description: "Prepares negotiation packets using provider performance data, cost analytics, and quality scores from claims and QARR/HEDIS data.",
    tag: "Provider Ops / Contracting",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Provider Leakage Analyzer Agent",
    description: "Identifies out-of-network referral or service leakage by comparing in-network claim expectations with actual billed patterns.",
    tag: "Network Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Case Classification Agent",
    description: "Automatically classifies incoming grievances and appeals based on category, urgency, and regulatory compliance timelines.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Grievance Sentiment Analysis Agent",
    description: "Analyzes grievance narratives and call transcripts using NLP to detect escalation risk and negative sentiment.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Grievance Root Cause Agent",
    description: "Analyzes grievances across time and regions, identifying recurring operational, benefit, or access issues from structured and free text data.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Regulatory Response Generator Agent",
    description: "Auto-generates time-bound response letters (e.g., 24h for expedited appeals) based on regulatory templates, member case details, and decision rules.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Evidence Compilation Agent",
    description: "Gathers all necessary documentation (clinical notes, auths, SOPs) tied to a grievance or appeal to support faster adjudication.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Decision Recommendation Agent",
    description: "Creates a clear, member-facing explanation of denial or approval using medical necessity criteria, benefit design, and clinical evidence.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Case Validation Agent",
    description: "Performs various validations against the case such as timeliness check, location determination, medical necessity check, etc.",
    tag: "Appeals & Grievances",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Stars Improvement Opportunity Agent",
    description: "Detects underperforming HEDIS/CAHPS measures by analyzing provider- and region-specific gaps, suggesting targeted interventions.",
    tag: "Quality / Stars",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "HEDIS Benchmark Analyzer Agent",
    description: "Compares plan-level HEDIS performance to national benchmarks and recommends targeted interventions.",
    tag: "Quality / Stars",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Eligibility Verification Agent",
    description: "Checks real-time insurance eligibility using payer APIs and returns coverage status, copay, and deductible for scheduled services.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Pre-Authorization Assistant Agent",
    description: "Prepares and submits prior auth requests for planned procedures using EHR notes and payer-specific criteria.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Charge Capture Audit Agent",
    description: "Cross-checks clinical documentation and billing codes to identify undercoding or missed charges. Uses EHR and claims data.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Claims Scrubbing Agent",
    description: "Validates outgoing claims against payer rules and historical denials. Flags likely rejections before submission.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Denial Appeal Letter Agent",
    description: "Drafts evidence-based denial appeals using medical records, payer guidelines, and authorization history.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Patient Billing Inquiry Agent",
    description: "Provides self-service responses to patient billing questions by pulling EOBs, CPT codes, and payment history.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Price Estimation Agent",
    description: "Estimates out-of-pocket costs using eligibility data, plan design, and service codes. Supports compliance with transparency rules.",
    tag: "Revenue Cycle Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Chart Abstraction Agent",
    description: "Extracts key clinical data from medical records, such as diagnosis, medications, test, treatment and procedures for efficient clinical decision-making.",
    tag: "Clinical Document Processing",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Lab Values Extraction Agent",
    description: "Identifies and extracts relevant lab results from medical records, organising them into structured data for quick reference and analysis.",
    tag: "Clinical Document Processing",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Form Data Extraction Agent",
    description: "Captures and organizes key information from structured forms, such as intake forms transforming them into easily accessible structured data. Currently supports only form per pdf/document uploaded.",
    tag: "Clinical Document Processing",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Prior Auth Extraction Agent",
    description: "Extracts key details from PA records, such as service request forms, clinical attachments for efficient clinical decision-making and streamlining approval process.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Guideline Retrieval Agent",
    description: "Locates and retrieves relevant clinical guidelines from policy documents for checking medical necessity ensuring quick-access to up-to-date criteria for informed clinical decision-making.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "HEDIS Care Gap Clinical Entity Extraction Agent",
    description: "Identifies key clinical concepts like symptoms, diagnoses, medications, PHI and procedures from medical documents, structuring them for efficient clinical decision making.",
    tag: "HEDIS Care Gap",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Precall Summarization Agent",
    description: "Generates concise, data driven summaries for care managers by analyzing member assessment forms and profile information, providing actionable insights for efficient pre-call preparation.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "DAR Note Creation Agent",
    description: "Summarizes member communications and care manager calls into Decision-Action-Response notes.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Call Summarization Agent",
    description: "Creates a simple summary from the call made by the care manager.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Care Plan Creation Agent",
    description: "Creates or updates care plans from member information and communications.",
    tag: "Care Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Protocol Summarization Agent",
    description: "Analyzes clinical trial protocols to extract and condense key elements, such as eligibility criteria, providing concise overviews for streamlined trial review and planning.",
    tag: "Clinical Research",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "IE Criteria Simplification Agent",
    description: "The IE Criteria Simplification Agent extracts and simplifies the eligibility criteria from clinical trial protocols, presenting clear and concise summaries to facilitate quicker participant screening and recruitment.",
    tag: "Clinical Research",
    version: "1.0",
    flow_id: "d86928f5-e518-4c0a-adc5-8ad63cb325cf"
  },
  {
    name: "IE Criteria Structuring Agent",
    description: "The IE Criteria Structuring Agent organizes and transforms clinical trial eligibility criteria into a structured, standardized format, enabling efficient participant screening and data analysis for patient recruitment.",
    tag: "Clinical Research",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Clinical Summarization Agent",
    description: "The Clinical Document Summarization Agent extracts and condenses essential information from lengthy clinical documents, such as progress notes or discharge summaries, to provide concise, easy-to-understand overviews for quick clinical review.",
    tag: "Clinical Document Processing",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Content Simplification Agent",
    description: "Simplifies clinical content to various levels (e.g., 4th grade, high school).",
    tag: "Clinical Document Processing",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "HEDIS Insights Generation Agent",
    description: "Analyzes healthcare data to extract and generate actionable insights related to HEDIS measures, supporting quality improvement and compliance efforts.",
    tag: "HEDIS Care Gap",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "HEDIS Summarization Agent",
    description: "Compiles and condenses medical records, providing concise summaries of performance measures related to HEDIS and compliance status to support quality assessment and decision-making.",
    tag: "HEDIS Care Gap",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Connectivity Agent",
    description: "Establishes secure connections to different data sources like Sharepoint, Azure, S3, Databricks, and Snowflake, enabling seamless data integration and real-time access for downstream applications and analytics.",
    tag: "Data Integration",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "EMR Connectivity Agent",
    description: "Securely connects to multiple EMR systems, facilitating data exchange and real-time access to patient records for integrated clinical workflows.",
    tag: "Data Integration",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Multi-Document Search Agent",
    description: "Enables efficient querying across multiple documents, retrieving relevant information from diverse data sources to support comprehensive analysis and decision-making.",
    tag: "Data Integration",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Document Question Answering Agent",
    description: "Performs QA on individual documents by analyzing content and providing precise, context-based responses to user queries for accurate and efficient information retrieval.",
    tag: "Data Integration",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Relation Extraction Agent",
    description: "Identifies and extracts relationships between clinical entities, such as treatments, and their dates, from medical documents to support deeper data analysis and knowledge discovery.",
    tag: "Clinical NLP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Entity Normalization Agent",
    description: "Standardizes extracted clinical terms, mapping them to unified medical terminologies or codes (e.g., SNOMED CT, ICD-10) to ensure consistency and improve data interoperability across systems.",
    tag: "Clinical NLP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Negation Detection Agent",
    description: "Identifies and correctly interprets negations in clinical texts, distinguishing between affirmed and negated concepts to ensure accurate data extraction and analysis.",
    tag: "Clinical NLP",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Clinical Note Classification Agent",
    description: "Classifies clinical text into categories like disease characteristics, medications, and patient characteristics categorizes enabling streamlined analysis.",
    tag: "Clinical Research",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Prior Auth Recommendation Agent",
    description: "Provide recommendations on prior authorization approvals based on the adjudication, streamlining decision-making and ensuring compliance with payer requirements.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Auth Guideline Adjudication Agent",
    description: "Evaluates prior authorization requests against clinical guidelines and payer policies to determine compliance, supporting accurate adjudication.",
    tag: "Utilization Management",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "PHI/PII Identification Agent",
    description: "Identifies and extracts sensitive personal health information (PHI) from unstructured text data.",
    tag: "Data Privacy & Security",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "PHI Redaction Agent",
    description: "Detects and removes PHI and PII from images or text documents.",
    tag: "Data Privacy & Security",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Speech Transcription Agent",
    description: "Transcribes speech into JSON or text format, enabling structured data extraction and facilitating downstream processing.",
    tag: "Communication",
    version: "1.0",
    flow_id: ""
  },
  {
    name: "Interactive Voice Agent",
    description: "Converts speech to text and text to speech from various conversations such as a Payer call center agent or a member having a conversation with a medical care provider.",
    tag: "Communication",
    version: "1.0",
    flow_id: ""
  }
];

function slugifyToFileName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 64);
}

export const STATIC_MARKETPLACE_AGENTS: AgentSpecItem[] = RAW_AGENTS_LIST.map(
  (a) => ({
    folder_name: "static_agents",
    file_name: slugifyToFileName(a.name),
    flow_id: a.flow_id || undefined,
    spec: {
      name: a.name,
      description: a.description,
      tags: a.tag ? [a.tag] : [],
      version: a.version,
      flow_id: a.flow_id || undefined,
    },
  }),
);