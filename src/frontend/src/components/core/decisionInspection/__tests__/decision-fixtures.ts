/**
 * Decision evidence as the backend sends it, captured from real Smart Router
 * and Decision Model runs (usage trimmed) plus the failure shapes the router
 * records for refusals, malformed answers and operational errors.
 */

const ROUTES = [
  {
    id: "category_5_result",
    label: "Billing",
    description: "Payments, invoices, refunds",
  },
  {
    id: "category_6_result",
    label: "Technical",
    description: "Bugs, errors, outages",
  },
];

const POLICY = {
  kind: "choice",
  options: ROUTES,
  minimum_probability: 0.5,
  route_thresholds: { category_5_result: 0.5, category_6_result: 0.5 },
  error_action: "Route to Else",
};

export const acceptedChoice = {
  ...POLICY,
  error_action: "Stop with error",
  activated_branch: "category_5_result",
  result: {
    kind: "choice",
    provider: "OpenAI",
    model: "gpt-6-luna",
    model_source: "response",
    status: "success",
    probabilities: { category_5_result: 1.0, category_6_result: 0.0 },
    selected_option: "category_5_result",
    confidence: 1.0,
    request_id: "req_bec3ccfa44b14cf8af0cf870fbd56fe9",
  },
  top_outcome: "category_5_result",
  applied_threshold: 0.5,
  reason: "accepted",
};

export const belowThreshold = {
  ...POLICY,
  minimum_probability: 0.99,
  route_thresholds: { category_5_result: 0.99, category_6_result: 0.99 },
  activated_branch: "default_result",
  result: {
    kind: "choice",
    provider: "OpenAI",
    model: "gpt-6-luna",
    model_source: "response",
    status: "success",
    probabilities: { category_5_result: 0.78, category_6_result: 0.22 },
    selected_option: "category_5_result",
  },
  top_outcome: "category_5_result",
  applied_threshold: 0.99,
  reason: "below_minimum_probability",
};

export const tied = {
  ...POLICY,
  activated_branch: "default_result",
  result: {
    kind: "choice",
    provider: "OpenAI",
    model: "gpt-6-luna",
    model_source: "request",
    status: "success",
    probabilities: { category_5_result: 0.5, category_6_result: 0.5 },
  },
  reason: "tied_top_probability",
};

export const noulAccepted = {
  kind: "noul",
  options: [
    { id: "yes_result", label: "Yes", description: "" },
    { id: "no_result", label: "No", description: "" },
  ],
  minimum_probability: 0.6,
  route_thresholds: { yes_result: 0.6, no_result: 0.6 },
  activated_branch: "yes_result",
  error_action: "Stop with error",
  result: {
    kind: "noul",
    provider: "OpenAI",
    model: "gpt-6-luna",
    model_source: "response",
    status: "success",
    probability_true: 0.98,
  },
  route_probabilities: { yes_result: 0.98, no_result: 0.02 },
  top_outcome: "yes_result",
  applied_threshold: 0.6,
  reason: "accepted",
};

export const scoreAccepted = {
  kind: "score",
  options: [
    { id: "level_7_result", label: "Low", description: "Can wait" },
    { id: "level_8_result", label: "Medium", description: "Soon" },
    { id: "level_9_result", label: "High", description: "Urgent" },
  ],
  minimum_probability: null,
  route_thresholds: {},
  activated_branch: "level_9_result",
  error_action: "Stop with error",
  result: {
    kind: "score",
    provider: "OpenAI",
    model: "gpt-6-luna",
    model_source: "response",
    status: "success",
    probabilities: {
      level_7_result: 0.0,
      level_8_result: 0.01,
      level_9_result: 0.99,
    },
    score: 1.99,
    confidence: 0.99,
  },
  reason: "accepted",
};

export const refusedToElse = {
  ...POLICY,
  activated_branch: "default_result",
  result: {
    kind: "choice",
    provider: "Perplexity",
    model: "pplx-decider-latest",
    model_source: "response",
    status: "refusal",
  },
  reason: "refusal",
};

export const malformedToElse = {
  ...POLICY,
  activated_branch: "default_result",
  reason: "evaluation_error",
  error: {
    category: "invalid_response",
    message:
      "OpenAI sent an answer Langflow couldn't read (request req_1). Try again.",
  },
};

export const transportStopped = {
  ...POLICY,
  error_action: "Stop with error",
  activated_branch: null,
  reason: "evaluation_error",
  error: {
    category: "transport",
    message: "Langflow couldn't reach OpenAI. Check the network and try again.",
  },
};

export const decisionModelScore = {
  kind: "score",
  provider: "OpenAI",
  model: "gpt-6-luna",
  model_source: "response",
  status: "success",
  probabilities: { low: 0.0, medium: 0.0, high: 1.0 },
  score: 2.0,
  confidence: 1.0,
  request_id: "req_24c2702912814e3ea5e74aba6e686004",
  request: {
    kind: "score",
    question: "How urgent is this message?",
    levels: [
      { id: "low", label: "Low" },
      { id: "medium", label: "Medium" },
      { id: "high", label: "High" },
    ],
  },
};

export const decisionModelNoulRefusal = {
  kind: "noul",
  provider: "TypeSafe",
  model: "jev-latest",
  model_source: "response",
  status: "refusal",
  refusal: "<img src=x onerror=alert(1)> I can't judge this content.",
  request: { kind: "noul", question: "Is this safe?" },
};

// A Decision Model asked two questions at once, as the backend serializes it.
export const decisionModelBatch = {
  answers: {
    team: {
      kind: "choice",
      provider: "OpenRouter",
      model: "typesafe/jev-latest",
      model_source: "response",
      status: "success",
      probabilities: { billing: 0.9, support: 0.1 },
      selected_option: "billing",
      request_id: "gen-1",
    },
    urgent: {
      kind: "noul",
      provider: "OpenRouter",
      model: "typesafe/jev-latest",
      model_source: "response",
      status: "refusal",
      request_id: "gen-1",
    },
  },
  request_id: "gen-1",
  request: {
    questions: {
      team: {
        kind: "choice",
        question: "Which team should take this?",
        options: [
          { id: "billing", label: "Billing" },
          { id: "support", label: "Support" },
        ],
      },
      urgent: { kind: "noul", question: "Is this urgent?" },
    },
  },
};
