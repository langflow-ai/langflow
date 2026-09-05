import { extractApiErrorMessages } from "../apiError";

describe("extractApiErrorMessages", () => {
  it("returns a default message for non-object errors", () => {
    expect(extractApiErrorMessages(null)).toEqual([
      "An unknown error occurred",
    ]);
    expect(extractApiErrorMessages(undefined)).toEqual([
      "An unknown error occurred",
    ]);
    expect(extractApiErrorMessages("boom")).toEqual([
      "An unknown error occurred",
    ]);
    expect(extractApiErrorMessages(123)).toEqual(["An unknown error occurred"]);
  });

  it("prefers response.data.detail when it is a string", () => {
    const error = {
      response: { data: { detail: "Server not found" } },
      message: "Network Error",
    };

    expect(extractApiErrorMessages(error)).toEqual(["Server not found"]);
  });

  it("extracts msg fields from validation-error arrays", () => {
    const error = {
      response: {
        data: {
          detail: [{ msg: "Field 'name' is required" }, { msg: "Bad input" }],
        },
      },
    };

    expect(extractApiErrorMessages(error)).toEqual([
      "Field 'name' is required",
      "Bad input",
    ]);
  });

  it("supports arrays mixing strings and objects", () => {
    const error = {
      response: {
        data: {
          detail: ["First", { msg: "Second" }],
        },
      },
    };

    expect(extractApiErrorMessages(error)).toEqual(["First", "Second"]);
  });

  it("JSON-stringifies array objects without a msg field", () => {
    const error = {
      response: {
        data: {
          detail: [{ code: 500, info: "crash" }],
        },
      },
    };

    expect(extractApiErrorMessages(error)).toEqual([
      '{"code":500,"info":"crash"}',
    ]);
  });

  it("falls back to error.message when array detail has no usable messages", () => {
    const error = {
      response: {
        data: {
          detail: ["", { msg: "" }],
        },
      },
      message: "Request failed",
    };

    expect(extractApiErrorMessages(error)).toEqual(["Request failed"]);
  });

  it("falls back to error.message when detail is an empty array", () => {
    const error = {
      response: {
        data: {
          detail: [],
        },
      },
      message: "Request failed",
    };

    expect(extractApiErrorMessages(error)).toEqual(["Request failed"]);
  });

  it("falls back to error.message when no detail is present", () => {
    expect(extractApiErrorMessages({ message: "Network Error" })).toEqual([
      "Network Error",
    ]);
  });

  it("always returns at least one message", () => {
    const msgs = extractApiErrorMessages({});
    expect(Array.isArray(msgs)).toBe(true);
    expect(msgs.length).toBeGreaterThan(0);
  });

  it("surfaces the message of a structured detail object", () => {
    const error = {
      response: {
        data: {
          detail: {
            error_code: "tier_limit_reached",
            message: "Your plan allows 3 projects.",
            resource: "projects",
            limit: 3,
            current: 3,
            tier: "trial",
          },
        },
      },
      message: "Request failed with status code 403",
    };

    expect(extractApiErrorMessages(error)).toEqual([
      "Your plan allows 3 projects.",
    ]);
  });

  it("falls back to error.message when a detail object has no message", () => {
    const error = {
      response: { data: { detail: { error_code: "tier_limit_reached" } } },
      message: "Request failed with status code 403",
    };

    expect(extractApiErrorMessages(error)).toEqual([
      "Request failed with status code 403",
    ]);
  });
});
