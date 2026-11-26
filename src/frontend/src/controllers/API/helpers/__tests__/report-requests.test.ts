import { checkDuplicateRequestAndStoreRequest } from "../check-duplicate-requests";

beforeEach(() => localStorage.clear());
afterEach(() => jest.restoreAllMocks());

it.each([
  "/api/v1/projects/project/reports",
  "/api/v1/projects/project/reports/flow/report",
  "/api/v1/projects/project/reports/flow/report/download/json",
])("allows an immediate report retry or reopen at %s", (url) => {
  jest.spyOn(Date, "now").mockReturnValue(1000);
  const request = { url, method: "get" };
  checkDuplicateRequestAndStoreRequest(request);
  expect(() => checkDuplicateRequestAndStoreRequest(request)).not.toThrow();
});
