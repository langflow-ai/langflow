import { decorateWxoUrl } from "../decorate-wxo-url";

describe("decorateWxoUrl", () => {
  it("appends UTM params to an IBM URL with no existing query", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/products/watsonx-orchestrate",
    );
    const parsed = new URL(result);
    expect(parsed.searchParams.get("utm_source")).toBe("langflow");
    expect(parsed.searchParams.get("utm_medium")).toBe("integration");
    expect(parsed.searchParams.get("utm_campaign")).toBe("wxo-integration");
  });

  it("preserves fragment identifier and places query before it", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/products/watsonx-orchestrate#pricing",
    );
    expect(result).toMatch(/\?[^#]*#pricing$/);
    const parsed = new URL(result);
    expect(parsed.hash).toBe("#pricing");
    expect(parsed.searchParams.get("utm_source")).toBe("langflow");
  });

  it("merges with existing query parameters without duplicating them", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started",
    );
    const parsed = new URL(result);
    expect(parsed.searchParams.get("topic")).toBe("api-getting-started");
    expect(parsed.searchParams.get("utm_source")).toBe("langflow");
    expect(parsed.searchParams.get("utm_medium")).toBe("integration");
  });

  it("adds utm_content when provided", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/products/watsonx-orchestrate",
      "signup-pricing",
    );
    const parsed = new URL(result);
    expect(parsed.searchParams.get("utm_content")).toBe("signup-pricing");
  });

  it("omits utm_content when not provided", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/products/watsonx-orchestrate",
    );
    expect(new URL(result).searchParams.has("utm_content")).toBe(false);
  });

  it("overwrites any pre-existing utm_source to avoid duplication", () => {
    const result = decorateWxoUrl(
      "https://www.ibm.com/foo?utm_source=other&utm_medium=email",
    );
    const parsed = new URL(result);
    expect(parsed.searchParams.getAll("utm_source")).toEqual(["langflow"]);
    expect(parsed.searchParams.getAll("utm_medium")).toEqual(["integration"]);
  });

  it("returns non-IBM URLs unchanged", () => {
    const url = "https://example.com/path?a=1";
    expect(decorateWxoUrl(url)).toBe(url);
  });

  it("does not match hostnames that only contain 'ibm.com' as a substring", () => {
    const url = "https://notibm.com/path";
    expect(decorateWxoUrl(url)).toBe(url);
  });

  it("returns the input unchanged when the URL cannot be parsed", () => {
    const url = "not a url";
    expect(decorateWxoUrl(url)).toBe(url);
  });

  it("decorates subdomains of ibm.com", () => {
    const result = decorateWxoUrl("https://www.ibm.com/anything");
    expect(new URL(result).searchParams.get("utm_source")).toBe("langflow");
  });
});
