import { buildShareablePlaygroundUrl } from "../shareable-playground-url";

describe("buildShareablePlaygroundUrl", () => {
  it("should join the origin and the playground path with a single slash", () => {
    expect(
      buildShareablePlaygroundUrl("http://localhost:7840", "/", "flow-1"),
    ).toBe("http://localhost:7840/playground/flow-1");
  });

  it("should keep the app base path when the app is served under one", () => {
    expect(
      buildShareablePlaygroundUrl("https://example.com", "/langflow", "flow-1"),
    ).toBe("https://example.com/langflow/playground/flow-1");
    expect(
      buildShareablePlaygroundUrl(
        "https://example.com",
        "/langflow/",
        "flow-1",
      ),
    ).toBe("https://example.com/langflow/playground/flow-1");
  });

  it("should encode characters that are not valid in a URL path", () => {
    expect(
      buildShareablePlaygroundUrl("http://localhost:7840", "/", "a b"),
    ).toBe("http://localhost:7840/playground/a%20b");
  });
});
