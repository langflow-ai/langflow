import type { ConnectionRead } from "@/controllers/API/queries/connections/use-get-connections";
import {
  accountLabel,
  buildConnectionOptions,
  connectionHandle,
  identityKindOf,
  identityMatches,
  missingScopesFor,
  shortScope,
} from "../helpers/connection-options";

const CALENDAR_READ =
  "https://www.googleapis.com/auth/calendar.events.readonly";
const GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send";

function connection(overrides: Partial<ConnectionRead> = {}): ConnectionRead {
  return {
    id: "c1",
    owner_id: "u1",
    ownership_mode: "user",
    provider_key: "google",
    name: "work",
    display_name: "Work Google",
    status: "ready",
    health: "healthy",
    granted_scopes: [CALENDAR_READ],
    executing_identity: { identity: "user_delegated" },
    allow_non_interactive: false,
    has_credentials: true,
    health_checked_at: null,
    created_at: "2026-09-16T10:00:00",
    updated_at: "2026-09-16T10:00:00",
    ...overrides,
  };
}

describe("shortScope", () => {
  it("keeps the last segment of a URL scope", () => {
    expect(shortScope(CALENDAR_READ)).toBe("calendar.events.readonly");
  });

  it("leaves bare scope names alone", () => {
    expect(shortScope("chat:write")).toBe("chat:write");
  });

  it("does not collapse a trailing slash into an empty label", () => {
    expect(shortScope("https://graph.microsoft.com/Mail.Send/")).toBe(
      "Mail.Send",
    );
  });
});

describe("connectionHandle", () => {
  it("is the portable provider/name handle the flow stores", () => {
    expect(connectionHandle(connection())).toBe("google/work");
  });
});

describe("missingScopesFor", () => {
  it("returns only the required scopes that were never granted", () => {
    expect(missingScopesFor(connection(), [CALENDAR_READ, GMAIL_SEND])).toEqual(
      [GMAIL_SEND],
    );
  });

  it("is empty when every required scope is granted", () => {
    expect(missingScopesFor(connection(), [CALENDAR_READ])).toEqual([]);
  });

  it("treats a field with no required scopes as covered", () => {
    expect(missingScopesFor(connection({ granted_scopes: [] }), [])).toEqual(
      [],
    );
  });
});

describe("buildConnectionOptions", () => {
  it("marks a ready connection that covers every scope as usable", () => {
    const [option] = buildConnectionOptions([connection()], [CALENDAR_READ]);
    expect(option).toMatchObject({
      handle: "google/work",
      usable: true,
      missingScopes: [],
      unusableReason: undefined,
    });
  });

  it("explains a missing scope instead of dropping the connection", () => {
    const [option] = buildConnectionOptions([connection()], [GMAIL_SEND]);
    expect(option.usable).toBe(false);
    expect(option.missingScopes).toEqual([GMAIL_SEND]);
    expect(option.unusableReason).toBe("Missing gmail.send");
  });

  it("reports a status that blocks the run before scope coverage", () => {
    const revoked = connection({ status: "revoked" });
    const [option] = buildConnectionOptions([revoked], [GMAIL_SEND]);
    expect(option.unusableReason).toBe("Connection is revoked");
  });

  it("lists usable connections first, then the most recently updated", () => {
    const options = buildConnectionOptions(
      [
        connection({
          id: "a",
          name: "older",
          updated_at: "2026-09-10T10:00:00",
        }),
        connection({ id: "b", name: "revoked", status: "revoked" }),
        connection({
          id: "c",
          name: "newer",
          updated_at: "2026-09-16T12:00:00",
        }),
      ],
      [CALENDAR_READ],
    );
    expect(options.map((option) => option.handle)).toEqual([
      "google/newer",
      "google/older",
      "google/revoked",
    ]);
  });

  it("returns nothing when the provider has no connections", () => {
    expect(buildConnectionOptions([], [CALENDAR_READ])).toEqual([]);
  });
});

describe("accountLabel", () => {
  it("prefers the connected account's display name", () => {
    const row = connection({
      executing_identity: {
        identity: "user_delegated",
        account: { id: "123", display: "eric@example.com" },
      },
    });
    expect(accountLabel(row)).toBe("eric@example.com");
  });

  it("falls back to the connection's display name", () => {
    expect(accountLabel(connection())).toBe("Work Google");
  });
});

describe("identity kind", () => {
  const botConnection = connection({
    executing_identity: { identity: "bot" },
  });

  it("maps a delegated account to the user kind and everything else to instance", () => {
    expect(identityKindOf(connection())).toBe("user");
    expect(identityKindOf(botConnection)).toBe("instance");
    expect(
      identityKindOf(
        connection({ executing_identity: { identity: "service" } }),
      ),
    ).toBe("instance");
  });

  it("accepts any connection when the field does not constrain the identity", () => {
    expect(identityMatches(botConnection, undefined)).toBe(true);
    expect(identityMatches(botConnection, "any")).toBe(true);
  });

  it("rejects a connection whose identity is not the one the field runs as", () => {
    expect(identityMatches(botConnection, "user")).toBe(false);
    expect(identityMatches(connection(), "instance")).toBe(false);
  });

  it("explains the identity mismatch before the scope check", () => {
    const [option] = buildConnectionOptions(
      [botConnection],
      [GMAIL_SEND],
      "user",
    );
    expect(option.usable).toBe(false);
    expect(option.unusableReason).toBe("Runs as the instance, not a user");
  });

  it("keeps a matching identity usable", () => {
    const [option] = buildConnectionOptions(
      [connection()],
      [CALENDAR_READ],
      "user",
    );
    expect(option.usable).toBe(true);
  });
});
