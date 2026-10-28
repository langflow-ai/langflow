import { api } from "../../../api";
import { listIntegrations, renewConnectionToken } from "../api";

jest.mock("../../../api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("../../../helpers/constants", () => ({
  getURL: (key: string) => `/api/v1/${key.toLowerCase()}`,
}));

it("sends a manual token replacement to the existing connection", async () => {
  const payload = {
    credentials: {
      access_token: "replacement-installation",
      expires_at: "2030-06-01T12:00:00Z",
    },
    allow_non_interactive: false,
  };
  jest
    .mocked(api.post)
    .mockResolvedValue({ data: { id: "connection-id", status: "ready" } });

  await expect(renewConnectionToken("connection-id", payload)).resolves.toEqual(
    { id: "connection-id", status: "ready" },
  );
  expect(api.post).toHaveBeenCalledWith(
    "/api/v1/connections/connection-id/token",
    payload,
  );
});

describe("listIntegrations", () => {
  it("preserves deployment context so the Slack token method can be offered", async () => {
    jest.mocked(api.get).mockResolvedValue({
      data: { providers: [], deployment_context: "self_managed" },
    });

    await expect(listIntegrations()).resolves.toEqual({
      providers: [],
      deployment_context: "self_managed",
    });
  });
});
