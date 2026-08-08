// Shape of the resolved A2A agent card served by
// GET /api/v1/a2a/{flow_id}/.well-known/agent-card.json (build_agent_card).
// Only the fields the tab renders are typed; the card carries more.
export type A2AInputSchema = {
  type?: string;
  properties?: Record<string, { type?: string; description?: string }>;
  required?: string[];
};

export type A2AAgentCard = {
  name?: string;
  description?: string;
  version?: string;
  url?: string;
  skills?: { inputSchema?: A2AInputSchema }[];
  // Present only for apikey folders; absent (exclude_none) otherwise.
  security?: Record<string, string[]>[];
  securitySchemes?: Record<
    string,
    { type?: string; name?: string; in?: string; description?: string }
  >;
};

// One row of the input contract, flattened from skills[0].inputSchema for display.
export type InputContractField = {
  name: string;
  type: string;
  required: boolean;
  description?: string;
};

export const cardInputContract = (
  card?: A2AAgentCard | null,
): InputContractField[] => {
  const schema = card?.skills?.[0]?.inputSchema;
  if (!schema?.properties) return [];
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties).map(([name, prop]) => ({
    name,
    type: prop?.type ?? "string",
    required: required.has(name),
    description: prop?.description,
  }));
};

// The card advertises apikey security only for apikey folders. oauth/none stay public.
export const cardRequiresApiKey = (card?: A2AAgentCard | null): boolean =>
  Array.isArray(card?.security) && card.security.length > 0;
