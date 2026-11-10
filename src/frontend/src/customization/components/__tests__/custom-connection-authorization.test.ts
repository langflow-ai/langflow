import type { OAuthRegistrationRead } from "@/controllers/API/queries/connections";
import { resolveRegistrationId } from "../custom-connection-authorization";

const registration = (
  overrides: Partial<OAuthRegistrationRead> = {},
): OAuthRegistrationRead => ({
  id: "google-work",
  provider: "google",
  profile: "user",
  context: "self_managed",
  client_type: "confidential",
  scopes: ["https://www.googleapis.com/auth/gmail.send"],
  allowed_tenants: [],
  ...overrides,
});

describe("resolveRegistrationId", () => {
  const work = registration();
  const personal = registration({ id: "google-personal" });
  const slackBot = registration({
    id: "slack-bot",
    provider: "slack",
    profile: "bot",
  });

  it("picks the registration for the provider and identity", () => {
    expect(
      resolveRegistrationId({
        provider: "google",
        identity: "user_delegated",
        registrations: [work, slackBot],
      }),
    ).toBe("google-work");
    expect(
      resolveRegistrationId({
        provider: "slack",
        identity: "bot",
        registrations: [work, slackBot],
      }),
    ).toBe("slack-bot");
  });

  it("keeps the caller's choice while it is still on offer", () => {
    expect(
      resolveRegistrationId({
        provider: "google",
        identity: "user_delegated",
        registrations: [work, personal],
        preferredId: "google-personal",
      }),
    ).toBe("google-personal");
  });

  it("falls back to the first candidate when the choice no longer applies", () => {
    expect(
      resolveRegistrationId({
        provider: "google",
        identity: "user_delegated",
        registrations: [work, personal],
        preferredId: "deleted",
      }),
    ).toBe("google-work");
  });

  it("is null when the provider has no registration, so the dialog can say so", () => {
    expect(
      resolveRegistrationId({
        provider: "microsoft",
        identity: "user_delegated",
        registrations: [work],
      }),
    ).toBeNull();
    // A user-profile registration cannot carry a bot identity.
    expect(
      resolveRegistrationId({
        provider: "google",
        identity: "bot",
        registrations: [work],
      }),
    ).toBeNull();
  });

  it("falls back to the provider id on a backend without the listing route", () => {
    expect(
      resolveRegistrationId({
        provider: "google",
        identity: "user_delegated",
        registrations: null,
      }),
    ).toBe("google");
  });
});
