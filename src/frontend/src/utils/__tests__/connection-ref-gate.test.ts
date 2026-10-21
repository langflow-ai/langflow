import type { APIClassType, APIDataType } from "@/types/api";
import {
  CONNECTION_REF_FIELD_TYPE,
  hideConnectionBackedComponents,
  isConnectionRefField,
  requiresConnectionRef,
} from "../connection-ref-gate";

const field = (overrides: Record<string, unknown>) => ({
  show: true,
  required: false,
  list: false,
  readonly: false,
  type: "str",
  ...overrides,
});

const component = (
  display_name: string,
  template: Record<string, unknown>,
): APIClassType =>
  ({
    display_name,
    description: "",
    template: { _type: "Component", ...template },
  }) as unknown as APIClassType;

const gmailSend = component("Gmail Send", {
  connection: field({
    type: "connection_ref",
    required: true,
    provider: "google",
    required_scopes: ["https://www.googleapis.com/auth/gmail.send"],
    capabilities: [],
  }),
  to: field({ required: true }),
});

// Legacy loader: optional connection_ref, still usable with pasted token JSON.
const gmailLoader = component("Gmail Loader", {
  connection: field({ type: "connection_ref", required: false }),
  json_string: field({ type: "str" }),
});

const chatInput = component("Chat Input", {
  input_value: field({ type: "str", required: true }),
});

describe("isConnectionRefField", () => {
  it("matches only the connection_ref field type", () => {
    expect(CONNECTION_REF_FIELD_TYPE).toBe("connection_ref");
    expect(isConnectionRefField({ type: "connection_ref" })).toBe(true);
    expect(isConnectionRefField({ type: "connect" })).toBe(false);
    expect(isConnectionRefField({ type: "str" })).toBe(false);
    expect(isConnectionRefField(undefined)).toBe(false);
    expect(isConnectionRefField(null)).toBe(false);
  });
});

describe("requiresConnectionRef", () => {
  it("is true when a connection_ref field is required", () => {
    expect(requiresConnectionRef(gmailSend)).toBe(true);
  });

  it("is false when the connection_ref field is optional", () => {
    expect(requiresConnectionRef(gmailLoader)).toBe(false);
  });

  it("is false when required is missing rather than true", () => {
    const loose = component("Loose", {
      connection: { type: "connection_ref", show: true },
    });
    expect(requiresConnectionRef(loose)).toBe(false);
  });

  it("is false for components without a connection_ref field", () => {
    expect(requiresConnectionRef(chatInput)).toBe(false);
  });

  it("is false for a missing component or template", () => {
    expect(requiresConnectionRef(undefined)).toBe(false);
    expect(requiresConnectionRef({} as APIClassType)).toBe(false);
  });
});

describe("hideConnectionBackedComponents", () => {
  const buildData = (): APIDataType => ({
    google: {
      GmailSendComponent: gmailSend,
      GmailLoaderComponent: gmailLoader,
    },
    input_output: { ChatInput: chatInput },
    slack: { SlackPostMessage: gmailSend },
  });

  it("removes components that require a connection", () => {
    const result = hideConnectionBackedComponents(buildData());

    expect(Object.keys(result.google)).toEqual(["GmailLoaderComponent"]);
    expect(Object.keys(result.input_output)).toEqual(["ChatInput"]);
  });

  it("keeps categories that end up empty", () => {
    const result = hideConnectionBackedComponents(buildData());

    expect(result).toHaveProperty("slack");
    expect(result.slack).toEqual({});
  });

  it("does not mutate the input and shares component payloads", () => {
    const data = buildData();
    const snapshot = JSON.parse(JSON.stringify(data));

    const result = hideConnectionBackedComponents(data);

    expect(data).toEqual(snapshot);
    expect(result).not.toBe(data);
    expect(result.google).not.toBe(data.google);
    expect(result.input_output).not.toBe(data.input_output);
    expect(result.google.GmailLoaderComponent).toBe(gmailLoader);
    expect(result.input_output.ChatInput).toBe(chatInput);
  });

  it("returns an empty object for empty data", () => {
    expect(hideConnectionBackedComponents({})).toEqual({});
  });
});
