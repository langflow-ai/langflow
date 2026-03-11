#!/usr/bin/env python3
"""Download flows from langflow-templates repo and add to dataset."""

import json
import os
import urllib.request
import urllib.error
import time
import sys

URLS = [
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/ai_support_response_generator/ai_support_response_generator.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/ingestion_router/ingestion_router.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/rag_article_in_web/rag_article_in_web.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/rag_article_in_web_with_agent/rag_article_in_web_with_agent.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/tool_based_rag/tool_based_rag.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/agentic_rag/vectorless_rag/vectorless_rag.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/ai_contract_risk_scanner/ai_contract_risk_scanner.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/chunk_classification/chunk_classification.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/data_extraction/data_extraction.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/document_classification/document_classification.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/generate_concise_overviews/generate_concise_overviews.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/information_retrieval/information_retrieval.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/marketing_content_creation/marketing_content_creation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/routing_sync/routing_sync.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/strategic_ebr_generator/strategic_ebr_generator.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/summarization/summarization.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/text_quantification/text_quantification.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/translation/translation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/document_intelligence/translation/agent_translation_template.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/semantic_memory/semantic_memory.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/t2d/talk_to_data.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/web_%26_workflow_automation/agentic_process_automation/agentic_process_automation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/web_%26_workflow_automation/ai_response_evaluation/ai_response_evaluation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/web_%26_workflow_automation/automated_data_entry/automated_data_entry.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/ai_patterns/web_%26_workflow_automation/terms_of_service_summarizer/terms_of_service_summarizer.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/customer_support_operations/call_classification_analytics/call_classification_analytics.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/customer_support_operations/customer_feedback_insight_generator/customer_feedback_insight_generator.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/customer_support_operations/smart_ticket_routing/smart_ticket_routing.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/customer_support_operations/sentiment_urgency_detection/sentiment_urgency_detection.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/customer_support_operations/fraud_flagging_analysis/fraud_flagging_analysis.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/data_and_analytics_augmentation/csv_query_assistant/csv_query_assistant.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/data_and_analytics_augmentation/customer_segmentation/customer_segmentation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/data_and_analytics_augmentation/dataframe_insights/dataframe_insights.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/data_and_analytics_augmentation/talk_to_csv/talk_to_csv.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/financial_services/fraud_detection/fraud_detection.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/hr_services/batch_resume_screener.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/sales_marketing_automation/lead_scoring/lead_scoring.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/sales_marketing_automation/marketing_content_creation/blog_outline_generator.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/sales_marketing_automation/personalized_outreach/personalized_outreach.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/sales_marketing_automation/seo_automation/seo_automation.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/productivity_%26_automation/personal_assistant.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/productivity_%26_automation/prd_draftsman.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/programming_%26_developer_productivity/code_explanation_%26_review/code_explanation_%26_review.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/business_funcions/programming_%26_developer_productivity/talk_to_apis/talk_to_APIs.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/data_science/sentiment_analysis.json",
    "https://raw.githubusercontent.com/Empreiteiro/langflow-templates/main/multimodal_functions/voice_notes_to_structured_text/voice_notes_to_structured_text.json",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "external_flows")
os.makedirs(OUT_DIR, exist_ok=True)

success = 0
failed = 0

for url in URLS:
    fname = url.split("/")[-1]
    # Handle URL-encoded names
    fname = urllib.parse.unquote(fname) if hasattr(urllib, 'parse') else fname
    outpath = os.path.join(OUT_DIR, fname)

    if os.path.exists(outpath):
        print("SKIP (exists): {}".format(fname))
        success += 1
        continue

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read()
        # Validate it's JSON
        flow = json.loads(data)
        with open(outpath, "wb") as f:
            f.write(data)
        print("OK: {}".format(fname))
        success += 1
    except Exception as e:
        print("FAIL: {} -> {}".format(fname, e))
        failed += 1

    time.sleep(0.3)

print("\nDone: {} success, {} failed out of {}".format(success, failed, len(URLS)))
