import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type {
  TriggerBulkAction,
  TriggerBulkRequest,
  TriggerBulkResult,
  TriggerEventRead,
  TriggerIngressRead,
  TriggerListParams,
  TriggerRead,
  TriggerSigningSecretRead,
} from "./types";

const triggers = () => getURL("TRIGGERS");
const one = (id: string) => `${triggers()}/${encodeURIComponent(id)}`;

/** The axios instance attaches auth and nothing else, so shapes are checked here. */
const asArray = <T>(value: unknown): T[] => (Array.isArray(value) ? value : []);

export async function listTriggers(
  params: TriggerListParams = {},
): Promise<TriggerRead[]> {
  const query = new URLSearchParams();
  if (params.flowId) query.set("flow_id", params.flowId);
  if (params.scope === "all") query.set("scope", "all");
  if (params.provider) query.set("provider", params.provider);
  if (params.state) query.set("state", params.state);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));
  const suffix = query.toString();
  const { data } = await api.get<TriggerRead[]>(
    suffix ? `${triggers()}?${suffix}` : triggers(),
  );
  return asArray<TriggerRead>(data);
}

export async function getTrigger(id: string): Promise<TriggerRead> {
  const { data } = await api.get<TriggerRead>(one(id));
  return data;
}

/** Resume, and the first enable of a `pending` trigger. */
export async function enableTrigger(id: string): Promise<TriggerRead> {
  const { data } = await api.post<TriggerRead>(`${one(id)}/enable`);
  return data;
}

/** Pause. */
export async function disableTrigger(id: string): Promise<TriggerRead> {
  const { data } = await api.post<TriggerRead>(`${one(id)}/disable`);
  return data;
}

export async function deleteTrigger(id: string): Promise<void> {
  await api.delete(one(id));
}

/** The server marks the payload as a test; the answer is the new event. */
export async function testTrigger(id: string): Promise<TriggerEventRead> {
  const { data } = await api.post<TriggerEventRead>(`${one(id)}/test`, {});
  return data;
}

export async function listTriggerEvents(
  id: string,
  options: { limit?: number; offset?: number } = {},
): Promise<TriggerEventRead[]> {
  const query = new URLSearchParams();
  if (options.limit !== undefined) query.set("limit", String(options.limit));
  if (options.offset) query.set("offset", String(options.offset));
  const suffix = query.toString();
  const { data } = await api.get<TriggerEventRead[]>(
    suffix ? `${one(id)}/events?${suffix}` : `${one(id)}/events`,
  );
  return asArray<TriggerEventRead>(data);
}

/** Appends a new event linked to `eventId`; the original is never changed. */
export async function replayTriggerEvent(
  id: string,
  eventId: string,
): Promise<TriggerEventRead> {
  const { data } = await api.post<TriggerEventRead>(`${one(id)}/replay`, {
    event_id: eventId,
  });
  return data;
}

export async function getTriggerIngress(
  id: string,
): Promise<TriggerIngressRead> {
  const { data } = await api.get<TriggerIngressRead>(`${one(id)}/ingress`);
  return data;
}

/** Creates or rotates the secret. The only response that carries it. */
export async function rotateTriggerSigningSecret(
  id: string,
): Promise<TriggerSigningSecretRead> {
  const { data } = await api.post<TriggerSigningSecretRead>(
    `${one(id)}/signing-secret`,
  );
  return data;
}

/** Superuser only. `dry_run` answers with the counts and changes nothing. */
export async function bulkTriggers(
  action: TriggerBulkAction,
  body: TriggerBulkRequest,
): Promise<TriggerBulkResult> {
  const { data } = await api.post<TriggerBulkResult>(
    `${triggers()}/bulk/${action}`,
    body,
  );
  return data;
}
