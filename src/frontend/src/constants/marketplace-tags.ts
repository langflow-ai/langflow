/**
 * Marketplace tags constants
 * Used by both the publish flow modal and marketplace filter page
 */

export const MARKETPLACE_TAGS = [
  'Patient Experience',
  'Provider Enablement',
  'Utilization Management',
  'Care Management',
  'Risk Adjustment',
  'Claims Operations',
  'Contracting',
  'RFP',
  'Member Engagement',
  'Population Health',
  'Provider Data Management',
  'Actuarial',
  'Finance',
  'Compliance',
  'Audit',
  'PBM',
  'Pharmacy',
  'Provider Ops',
  'Provider Contracting',
  'Network Management',
  'Appeals',
  'Grievances',
  'Quality',
  'Stars',
  'Revenue Cycle Management',
  'Utilization Management',
  'Care Gap',
  'Chart Review',
  'HEDIS Care Gap',
  'Clinical Research'
] as const;

export type MarketplaceTag = typeof MARKETPLACE_TAGS[number];
