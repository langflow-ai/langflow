import { AxiosError, AxiosHeaders } from "axios";
import { getAxiosErrorMessage } from "../get-axios-error-message";

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
