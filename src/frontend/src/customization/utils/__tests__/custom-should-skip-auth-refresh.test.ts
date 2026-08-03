import type { AxiosError } from "axios";
import { customShouldSkipAuthRefresh } from "../custom-should-skip-auth-refresh";

describe("customShouldSkipAuthRefresh", () => {
  it("never skips auth refresh in the OSS build", () => {
    const error = {
      response: { status: 403, data: { detail: "must_change_password" } },
    } as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(false);
  });
});
