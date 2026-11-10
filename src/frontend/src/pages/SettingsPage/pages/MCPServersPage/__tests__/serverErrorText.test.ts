import { serverErrorText, type Translate } from "../serverErrorText";

// Echo the key and its detail so each test sees which copy was chosen.
const t: Translate = (key, options) =>
  options?.detail ? `${key}(${options.detail})` : key;

describe("serverErrorText", () => {
  it.each([
    ["No tools found", "mcp.servers.statusNoTools"],
    ["Timeout when checking server tools", "mcp.servers.errorTimeout"],
  ])("translates the fixed message %s", (error, key) => {
    expect(serverErrorText(error, t)).toBe(key);
  });

  it.each([
    [
      "Configuration data error: bad JSON",
      "mcp.servers.errorConfigurationData(bad JSON)",
    ],
    ["Configuration error: no URL", "mcp.servers.errorConfiguration(no URL)"],
    ["Connection failed: refused", "mcp.servers.errorConnection(refused)"],
    ["System error: boom", "mcp.servers.errorSystem(boom)"],
    ["Runtime error: crashed", "mcp.servers.errorRuntime(crashed)"],
    ["Error loading server: 404", "mcp.servers.errorLoading(404)"],
  ])("translates the sentence around %s", (error, expected) => {
    expect(serverErrorText(error, t)).toBe(expected);
  });

  it("returns an unknown message unchanged", () => {
    expect(serverErrorText("Something new", t)).toBe("Something new");
  });
});
