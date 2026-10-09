import { checkDuplicateRequestAndStoreRequest } from "../check-duplicate-requests";

const get = (params: Record<string, unknown>) => ({
  url: "/api/v1/monitor/messages/sessions",
  method: "get",
  params,
});

describe("checkDuplicateRequestAndStoreRequest", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("rejects the same GET repeated within 300 ms", () => {
    checkDuplicateRequestAndStoreRequest(get({ offset: 0 }));

    expect(() =>
      checkDuplicateRequestAndStoreRequest(get({ offset: 0 })),
    ).toThrow("Duplicate request");
  });

  it("allows GETs to the same path with different query params", () => {
    checkDuplicateRequestAndStoreRequest(get({ offset: 0 }));

    expect(() =>
      checkDuplicateRequestAndStoreRequest(get({ offset: 100 })),
    ).not.toThrow();
  });
});
