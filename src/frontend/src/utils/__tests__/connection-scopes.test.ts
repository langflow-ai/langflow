import {
  activeRequiredScopes,
  type ConditionalScopeRequirement,
  isPythonTruthy,
  isScopeConditionActive,
  missingScopes,
  normalizeScope,
  templateInputValues,
  uniqueNormalizedScopes,
} from "../connection-scopes";

const MAIL_SEND = "https://graph.microsoft.com/Mail.Send";
const GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send";

// The Microsoft files actions and the Slack members action, as their bundles
// declare them.
const FILES_CONDITIONAL: ConditionalScopeRequirement[] = [
  {
    scope: "Files.Read.All",
    role: "optional",
    condition: { kind: "input_truthy", input: "drive_id" },
  },
  {
    scope: "Sites.Read.All",
    role: "optional",
    condition: { kind: "input_truthy", input: "site_id" },
  },
];
const SLACK_MEMBERS_CONDITIONAL: ConditionalScopeRequirement[] = [
  {
    scope: "groups:read",
    role: "optional",
    condition: { kind: "input_truthy", input: "channel_is_private" },
  },
  {
    scope: "users:read",
    role: "optional",
    condition: { kind: "input_truthy", input: "resolve_names" },
  },
];

describe("normalizeScope (mirrors ScopeSet._normalize)", () => {
  it("drops the Microsoft Graph prefix and ignores case", () => {
    expect(normalizeScope("microsoft", MAIL_SEND)).toBe("mail.send");
    expect(normalizeScope("microsoft", " mail.SEND ")).toBe("mail.send");
  });

  it("drops the Google prefix for both Google provider ids", () => {
    expect(normalizeScope("google", GMAIL_SEND)).toBe("gmail.send");
    expect(normalizeScope("google_workspace", GMAIL_SEND)).toBe("gmail.send");
  });

  it("keeps another provider's prefix, as the backend does", () => {
    expect(normalizeScope("slack", MAIL_SEND)).toBe(MAIL_SEND.toLowerCase());
    expect(normalizeScope("microsoft", GMAIL_SEND)).toBe(
      GMAIL_SEND.toLowerCase(),
    );
  });

  it("matches the prefix case-sensitively before folding case", () => {
    // `str.removeprefix` is exact, so an upper-cased URL keeps its prefix.
    expect(
      normalizeScope("microsoft", "HTTPS://GRAPH.MICROSOFT.COM/Mail.Send"),
    ).toBe("https://graph.microsoft.com/mail.send");
  });

  it("never conflates Slack user and bot scope names", () => {
    expect(normalizeScope("slack", "chat:write")).toBe("chat:write");
    expect(normalizeScope("slack", "chat:write")).not.toBe(
      normalizeScope("slack", "chat:write.customize"),
    );
  });
});

describe("missingScopes (mirrors ScopeSet.missing)", () => {
  it("treats a bare Microsoft scope as covering its URL form", () => {
    expect(missingScopes("microsoft", [MAIL_SEND], ["Mail.Send"])).toEqual([]);
  });

  it("matches regardless of case", () => {
    expect(missingScopes("slack", ["Chat:Write"], ["chat:write"])).toEqual([]);
  });

  it("reports what is missing in the spelling the action declared", () => {
    expect(
      missingScopes("microsoft", [MAIL_SEND, "Files.Read"], ["mail.send"]),
    ).toEqual(["Files.Read"]);
  });
});

describe("uniqueNormalizedScopes", () => {
  it("keeps the first spelling of scopes that normalize alike", () => {
    expect(
      uniqueNormalizedScopes("microsoft", [
        MAIL_SEND,
        "mail.send",
        "Files.Read",
      ]),
    ).toEqual([MAIL_SEND, "Files.Read"]);
  });
});

describe("isPythonTruthy", () => {
  it.each([
    [null, false],
    [undefined, false],
    [false, false],
    [0, false],
    [-0, false],
    ["", false],
    [[], false],
    [{}, false],
    [true, true],
    [1, true],
    [Number.NaN, true],
    ["0", true],
    ["false", true],
    [[0], true],
    [{ a: 1 }, true],
  ])("bool(%p) is %p", (value, expected) => {
    expect(isPythonTruthy(value)).toBe(expected);
  });
});

describe("isScopeConditionActive (mirrors ScopeCondition.is_active)", () => {
  it("input_present needs the input to exist with a non-null value", () => {
    const present = { kind: "input_present", input: "calendar_id" } as const;
    expect(isScopeConditionActive(present, { calendar_id: "" })).toBe(true);
    expect(isScopeConditionActive(present, { calendar_id: false })).toBe(true);
    expect(isScopeConditionActive(present, { calendar_id: null })).toBe(false);
    expect(isScopeConditionActive(present, { calendar_id: undefined })).toBe(
      false,
    );
    expect(isScopeConditionActive(present, {})).toBe(false);
  });

  it("input_truthy follows Python truthiness", () => {
    const truthy = { kind: "input_truthy", input: "drive_id" } as const;
    expect(isScopeConditionActive(truthy, { drive_id: "b!abc" })).toBe(true);
    expect(isScopeConditionActive(truthy, { drive_id: "" })).toBe(false);
    expect(isScopeConditionActive(truthy, {})).toBe(false);
  });

  it("ignores a condition it does not understand", () => {
    expect(
      isScopeConditionActive({ kind: "input_equals", input: "x" } as never, {
        x: true,
      }),
    ).toBe(false);
    expect(isScopeConditionActive(undefined, { x: true })).toBe(false);
  });
});

describe("activeRequiredScopes", () => {
  it("adds only the conditional scopes the inputs switch on", () => {
    expect(
      activeRequiredScopes("microsoft", ["Files.Read"], FILES_CONDITIONAL, {
        drive_id: "b!abc",
        site_id: "",
      }),
    ).toEqual(["Files.Read", "Files.Read.All"]);
  });

  it("adds Slack's private-channel and name-resolution scopes when toggled on", () => {
    expect(
      activeRequiredScopes(
        "slack",
        ["channels:read"],
        SLACK_MEMBERS_CONDITIONAL,
        {
          channel_is_private: true,
          resolve_names: false,
        },
      ),
    ).toEqual(["channels:read", "groups:read"]);
  });

  it("does not repeat a conditional scope the action already requires", () => {
    expect(
      activeRequiredScopes(
        "microsoft",
        ["https://graph.microsoft.com/Files.Read.All"],
        FILES_CONDITIONAL,
        { drive_id: "b!abc" },
      ),
    ).toEqual(["https://graph.microsoft.com/Files.Read.All"]);
  });

  it("returns the required scopes alone without conditional ones", () => {
    expect(activeRequiredScopes("google", [GMAIL_SEND], undefined, {})).toEqual(
      [GMAIL_SEND],
    );
  });
});

describe("templateInputValues", () => {
  it("reads each field's value by input name and skips non-field entries", () => {
    expect(
      templateInputValues({
        _type: "Component",
        drive_id: { type: "str", value: "b!abc" },
        site_id: { type: "str" },
        resolve_names: { type: "bool", value: true },
      }),
    ).toEqual({ drive_id: "b!abc", site_id: undefined, resolve_names: true });
  });

  it("returns nothing for a node without a template", () => {
    expect(templateInputValues(undefined)).toEqual({});
  });
});
