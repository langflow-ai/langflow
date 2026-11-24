import { AxiosError, AxiosHeaders } from "axios";
import {
  getAxiosErrorDetail,
  getAxiosErrorMessage,
} from "../get-axios-error-message";

function makeAxiosError(data: unknown, message = "Request failed"): AxiosError {
  const error = new AxiosError(message);
  error.response = {
    data,
    status: 422,
    statusText: "Unprocessable Entity",
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return error;
}

describe("getAxiosErrorMessage", () => {
  it("returns string detail from Axios error response", () => {
    const err = makeAxiosError({ detail: "Not found" });
    expect(getAxiosErrorMessage(err)).toBe("Not found");
  });

  it("returns joined msg fields when detail is a Pydantic validation error array", () => {
    const err = makeAxiosError({
      detail: [
        {
          type: "value_error",
          loc: ["body", "url"],
          msg: "Value error, URL hostname 'evil.com' is not allowed for provider 'watsonx-orchestrate'",
        },
      ],
    });
    expect(getAxiosErrorMessage(err)).toBe(
      "Value error, URL hostname 'evil.com' is not allowed for provider 'watsonx-orchestrate'",
    );
  });

  it("joins multiple validation errors with semicolons", () => {
    const err = makeAxiosError({
      detail: [
        { msg: "Field required", loc: ["body", "name"] },
        { msg: "Invalid URL", loc: ["body", "url"] },
      ],
    });
    expect(getAxiosErrorMessage(err)).toBe("Field required; Invalid URL");
  });

  it("falls back to err.message when detail is missing", () => {
    const err = makeAxiosError({});
    expect(getAxiosErrorMessage(err)).toBe("Request failed");
  });

  it("falls back to default message for non-Axios, non-Error values", () => {
    expect(getAxiosErrorMessage("random string")).toBe(
      "An unknown error occurred",
    );
  });

  it("returns Error.message for plain Error instances", () => {
    expect(getAxiosErrorMessage(new Error("boom"))).toBe("boom");
  });

  it("uses custom fallback when provided", () => {
    expect(getAxiosErrorMessage(null, "custom fallback")).toBe(
      "custom fallback",
    );
  });

  it("handles detail as an array of plain strings", () => {
    const err = makeAxiosError({ detail: ["error one", "error two"] });
    expect(getAxiosErrorMessage(err)).toBe("error one; error two");
  });
});

describe("getAxiosErrorDetail", () => {
  const fallback = "O servidor recusou a solicitação.";

  it.each([
    new AxiosError("Network Error"),
    new AxiosError("timeout of 30000ms exceeded"),
    makeAxiosError({}),
    makeAxiosError({ detail: null }),
    makeAxiosError({ detail: "" }),
    makeAxiosError({ detail: [] }),
    makeAxiosError({ detail: { unexpected: true } }),
    new Error("Network Error"),
    null,
  ])(
    "uses the translated fallback without usable server detail: %p",
    (error) => {
      expect(getAxiosErrorDetail(error, fallback)).toBe(fallback);
    },
  );

  it.each([
    ["Invalid handle", "Invalid handle"],
    [
      [{ msg: "Invalid handle" }, { msg: "Field required" }],
      "Invalid handle; Field required",
    ],
  ])("preserves server detail: %p", (detail, expected) => {
    expect(getAxiosErrorDetail(makeAxiosError({ detail }), fallback)).toBe(
      expected,
    );
  });
});
