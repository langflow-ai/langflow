import { AxiosError, type AxiosResponse } from "axios";
import {
  lastErrorText,
  triggerRefusalText,
} from "../helpers/trigger-error-text";

const t = (key: string) => `t:${key}`;

const refusal = (detail: unknown) =>
  new AxiosError("Request failed", "ERR_BAD_REQUEST", undefined, undefined, {
    status: 409,
    data: { detail },
  } as AxiosResponse);

describe("lastErrorText", () => {
  it("shows a coded error in the reader's language", () => {
    expect(
      lastErrorText(
        {
          last_error:
            "Invalid cron expression: a valid five-field cron expression is required.",
          last_error_code: "invalid_cron",
          reason: "config_invalid",
        },
        t,
      ),
    ).toBe("t:triggers.serverError.invalid_cron");
  });

  it.each([
    ["node_removed", "node_removed"],
    ["source_settings_changed", "source_settings_changed"],
    ["connection_not_authorized", "consent_required"],
  ] as const)(
    "does not repeat %s under the reason that already says it",
    (code, reason) => {
      expect(
        lastErrorText(
          { last_error: "English text", last_error_code: code, reason },
          t,
        ),
      ).toBeNull();
    },
  );

  it("still explains a removed node when the reason is a different one", () => {
    expect(
      lastErrorText(
        {
          last_error: "trigger node removed from the flow",
          last_error_code: "node_removed",
          reason: "error",
        },
        t,
      ),
    ).toBe("t:triggers.serverError.node_removed");
  });

  it.each([null, undefined, "some_future_code"])(
    "shows text without a known code (%s) as the server wrote it",
    (code) => {
      expect(
        lastErrorText(
          {
            last_error: "Provider returned 502",
            last_error_code: code,
            reason: "degraded",
          },
          t,
        ),
      ).toBe("Provider returned 502");
    },
  );

  it("shows nothing without an error, or once the trigger is ready to resume", () => {
    expect(
      lastErrorText(
        { last_error: null, last_error_code: null, reason: "paused" },
        t,
      ),
    ).toBeNull();
    expect(
      lastErrorText(
        {
          last_error: "connection_not_authorized",
          last_error_code: "connection_not_authorized",
          reason: "ready_to_resume",
        },
        t,
      ),
    ).toBeNull();
  });
});

describe("triggerRefusalText", () => {
  it("translates a coded refusal", () => {
    expect(
      triggerRefusalText(
        refusal({
          code: "background_runs_not_allowed",
          message: "Turn on 'Allow background runs' for the Slack connection…",
        }),
        t,
      ),
    ).toBe("t:triggers.serverError.background_runs_not_allowed");
  });

  it("falls back to the English message of a refusal without a known code", () => {
    expect(
      triggerRefusalText(
        refusal({ code: null, message: "The trigger no longer exists." }),
        t,
      ),
    ).toBe("The trigger no longer exists.");
  });

  it("still reads a plain string detail", () => {
    expect(triggerRefusalText(refusal("Not found"), t)).toBe("Not found");
  });

  it("says something went wrong when there is no detail", () => {
    expect(triggerRefusalText(new Error("boom"), t)).toBe(
      "t:triggers.errors.unknown",
    );
  });
});
