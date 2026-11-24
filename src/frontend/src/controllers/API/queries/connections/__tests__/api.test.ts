import { api } from "../../../api";
import { listIntegrations } from "../api";

jest.mock("../../../api", () => ({ api: { get: jest.fn() } }));
jest.mock("../../../helpers/constants", () => ({
  getURL: () => "/api/v1/integrations",
}));

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
