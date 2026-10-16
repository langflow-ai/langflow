import { api } from "../../../api";
import {
  bulkTriggers,
  listTriggerEvents,
  listTriggers,
  replayTriggerEvent,
  testTrigger,
} from "../api";

jest.mock("../../../api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
}));
jest.mock("../../../helpers/constants", () => ({
  getURL: () => "/api/v1/triggers",
}));

describe("triggers api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("lists across flows when no flow is given", async () => {
    jest.mocked(api.get).mockResolvedValue({ data: [] });

    await listTriggers();

    expect(api.get).toHaveBeenCalledWith("/api/v1/triggers");
  });

  it("encodes every filter into the query string", async () => {
    jest.mocked(api.get).mockResolvedValue({ data: [] });

    await listTriggers({
      flowId: "f 1",
      scope: "all",
      provider: "slack",
      state: "needs_reconnect",
      limit: 51,
      offset: 50,
    });

    expect(api.get).toHaveBeenCalledWith(
      "/api/v1/triggers?flow_id=f+1&scope=all&provider=slack&state=needs_reconnect&limit=51&offset=50",
    );
  });

  it("omits the default scope", async () => {
    jest.mocked(api.get).mockResolvedValue({ data: [] });

    await listTriggers({ scope: "mine" });

    expect(api.get).toHaveBeenCalledWith("/api/v1/triggers");
  });

  it("returns an empty list when the body is not an array", async () => {
    jest.mocked(api.get).mockResolvedValue({ data: { detail: "nope" } });

    await expect(listTriggers()).resolves.toEqual([]);
  });

  it("escapes the trigger id in a path segment", async () => {
    jest.mocked(api.get).mockResolvedValue({ data: [] });

    await listTriggerEvents("../x", { limit: 51 });

    expect(api.get).toHaveBeenCalledWith(
      "/api/v1/triggers/..%2Fx/events?limit=51",
    );
  });

  it("posts the replayed event id", async () => {
    jest.mocked(api.post).mockResolvedValue({ data: {} });

    await replayTriggerEvent("t1", "e1");

    expect(api.post).toHaveBeenCalledWith("/api/v1/triggers/t1/replay", {
      event_id: "e1",
    });
  });

  it("sends an empty test payload so the server marks it as a test", async () => {
    jest.mocked(api.post).mockResolvedValue({ data: {} });

    await testTrigger("t1");

    expect(api.post).toHaveBeenCalledWith("/api/v1/triggers/t1/test", {});
  });

  it("routes bulk actions by name", async () => {
    jest.mocked(api.post).mockResolvedValue({ data: {} });

    await bulkTriggers("pause", { provider: "slack", dry_run: true });

    expect(api.post).toHaveBeenCalledWith("/api/v1/triggers/bulk/pause", {
      provider: "slack",
      dry_run: true,
    });
  });
});
