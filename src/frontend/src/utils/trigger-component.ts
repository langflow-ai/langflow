import type { APIClassType } from "@/types/api";

/**
 * True for a trigger node, wherever the palette lists it. Core triggers sit in
 * the Triggers category, but a provider's triggers (Slack: On Message) sit in
 * that provider's group next to its actions; the server stamps every one of
 * them with `metadata.trigger_kind` from the loaded class.
 */
export function isTriggerComponent(
  component: APIClassType | undefined,
): boolean {
  // `metadata` is an object, which APIClassType's index signature does not
  // admit, so it is read through this one narrow view rather than widening the
  // palette type for every consumer.
  const metadata = (component as ComponentMetadataView | undefined)?.metadata;
  return typeof metadata?.trigger_kind === "string";
}

type ComponentMetadataView = { metadata?: { trigger_kind?: unknown } };
