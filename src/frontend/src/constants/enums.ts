/**
 * enum for the different types of nodes
 * @enum
 */
export enum TypeModal {
  TEXT = 1,
  PROMPT = 2,
}

export enum BuildStatus {
  BUILDING = "BUILDING",
  TO_BUILD = "TO_BUILD",
  BUILT = "BUILT",
  INACTIVE = "INACTIVE",
  ERROR = "ERROR",
}

export enum InputOutput {
  INPUT = "input",
  OUTPUT = "output",
}

export enum IOInputTypes {
  TEXT = "TextInput",
  FILE_LOADER = "FileLoader",
  KEYPAIR = "KeyPairInput",
  JSON = "JsonInput",
  STRING_LIST = "StringListInput",
}

export enum IOOutputTypes {
  TEXT = "TextOutput",
  PDF = "PDFOutput",
  CSV = "CSVOutput",
  IMAGE = "ImageOutput",
  JSON = "JsonOutput",
  KEY_PAIR = "KeyPairOutput",
  STRING_LIST = "StringListOutput",
  DATA = "DataOutput",
}

export enum EventDeliveryType {
  STREAMING = "streaming",
  POLLING = "polling",
  DIRECT = "direct",
}

/**
 * Deployment tweak policy, mirroring LANGFLOW_TWEAKS_POLICY.
 *
 * The per-field "editable via API" toggle is only enforced under "declared",
 * and only on flows whose author marked at least one field. Under "permissive"
 * the toggle records intent and nothing else; under "off" every tweak is
 * refused regardless of it. The protected-field floor applies in all three.
 */
export const TWEAKS_POLICIES = ["permissive", "declared", "off"] as const;

export type TweaksPolicy = (typeof TWEAKS_POLICIES)[number];

export const isTweaksPolicy = (value: unknown): value is TweaksPolicy =>
  typeof value === "string" &&
  (TWEAKS_POLICIES as readonly string[]).includes(value);
