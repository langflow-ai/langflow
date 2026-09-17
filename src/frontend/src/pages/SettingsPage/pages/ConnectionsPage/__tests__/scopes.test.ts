import type { IntegrationCapabilityRead } from "@/controllers/API/queries/connections";
import type { APIDataType } from "@/types/api";
import {
  findComponentByRef,
  partitionByCeiling,
  scopeRequirements,
  shortScope,
  uniqueScopes,
} from "../helpers/scopes";

const GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send";
const CALENDAR = "https://www.googleapis.com/auth/calendar.events";

const capability = (
  overrides: Partial<IntegrationCapabilityRead> = {},
): IntegrationCapabilityRead => ({
  id: "google.gmail.send",
  display_name: "Gmail: Send Email",
  policy_keys: ["integrations.google.gmail.send"],
  risk: "write",
  maturity: "ga",
  substrate: "sdk",
  identity: "user_delegated",
  auth_profile_id: "user",
  deployment_contexts: ["self_managed"],
  component_ref: "GmailSendComponent",
  allowed: true,
  ...overrides,
});

const types = {
  google: {
    "ext:google:GmailSendComponent@official": {
      template: {
        connection: {
          type: "connection_ref",
          required_scopes: [GMAIL_SEND],
          conditional_scopes: [{ scope: CALENDAR, input: "calendar_id" }],
        },
      },
    },
  },
} as unknown as APIDataType;

describe("shortScope", () => {
  it("shortens a URL scope and leaves a bare one alone", () => {
    expect(shortScope(GMAIL_SEND)).toBe("gmail.send");
    expect(shortScope("chat:write")).toBe("chat:write");
  });
});

describe("findComponentByRef", () => {
  it("matches the canonical key a bundle component is registered under", () => {
    expect(findComponentByRef(types, "GmailSendComponent")).toBeDefined();
  });

  it("returns nothing for an unknown ref or missing catalog", () => {
    expect(findComponentByRef(types, "Nope")).toBeUndefined();
    expect(findComponentByRef(undefined, "GmailSendComponent")).toBeUndefined();
  });
});

describe("scopeRequirements", () => {
  it("reads the scopes off the component's connection field", () => {
    expect(scopeRequirements([capability()], types)).toEqual([
      {
        capabilityId: "google.gmail.send",
        displayName: "Gmail: Send Email",
        requiredScopes: [GMAIL_SEND],
        conditionalScopes: [{ scope: CALENDAR, input: "calendar_id" }],
      },
    ]);
  });

  it("reports no scopes when the component is not loaded", () => {
    const [requirement] = scopeRequirements([capability()], undefined);
    expect(requirement.requiredScopes).toEqual([]);
  });
});

describe("uniqueScopes", () => {
  it("collects required and conditional scopes without duplicates", () => {
    expect(uniqueScopes(scopeRequirements([capability()], types))).toEqual([
      GMAIL_SEND,
      CALENDAR,
    ]);
  });
});

describe("partitionByCeiling", () => {
  it("asks only for what the registration allows", () => {
    expect(partitionByCeiling([GMAIL_SEND, CALENDAR], [GMAIL_SEND])).toEqual({
      requestable: [GMAIL_SEND],
      unavailable: [CALENDAR],
    });
  });

  it("passes everything through when no ceiling is known", () => {
    expect(partitionByCeiling([GMAIL_SEND], undefined)).toEqual({
      requestable: [GMAIL_SEND],
      unavailable: [],
    });
  });
});
