import { checkDuplicateRequestAndStoreRequest } from "../check-duplicate-requests";

const get = (params: Record<string, unknown>) => ({
  url: "/api/v1/monitor/messages/sessions",
  method: "get",
  params,
});

describe("checkDuplicateRequestAndStoreRequest", () => {
  beforeEach(() => {
    localStorage.clear();
    jest.spyOn(Date, "now").mockReturnValue(1000);
  });

  afterEach(() => {
    jest.restoreAllMocks();
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

  it.each([
    { url: "/api/v1/variables/" },
    { url: "/api/v1/variables/", params: { project_id: "project-1" } },
    { url: "/langflow/api/v1/variables/" },
  ])("allows consecutive variable-list refetches for $url", (request) => {
    const config = { ...request, method: "get" };
    checkDuplicateRequestAndStoreRequest(config);

    expect(() => checkDuplicateRequestAndStoreRequest(config)).not.toThrow();
  });
});
