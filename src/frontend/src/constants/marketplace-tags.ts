/**
 * Marketplace tags constants
 * Used by both the publish flow modal and marketplace filter page
 */

export const MARKETPLACE_TAGS = [
  "Actuarial / Finance",
  "Appeals & Grievances",
  "Care Management",
  "Claims Operations",
  "Clinical Document Processing",
  "Clinical NLP",
  "Clinical Research",
  "Clinical Quality",
  "Data Analytics",
  "Disease Management",
  "Drug Prior Authorization",
  "Electronic Health Records",
  "Fraud Detection",
  "Healthcare Compliance",
  "Medical Billing",
  "Patient Engagement",
  "Population Health",
  "Provider Network",
  "Quality Improvement",
  "Risk Adjustment",
  "Utilization Management",
] as const;

export type MarketplaceTag = typeof MARKETPLACE_TAGS[number];
