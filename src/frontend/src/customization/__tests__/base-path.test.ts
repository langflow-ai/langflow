import { normalizeBasePath } from "../base-path";

describe("frontend URL prefix", () => {
  afterEach(() => {
    document.querySelector("base")?.remove();
    jest.resetModules();
  });

  it.each(["/", "/langflow/", "/tools/langflow/"])(
    "uses %s for API requests, health checks, and copied URLs",
    (baseUrl) => {
      const base = document.createElement("base");
      base.href = baseUrl;
      document.head.appendChild(base);
      jest.resetModules();
      const prefix = baseUrl.replace(/\/$/, "");
      const config = require("../config-constants");
      const { getURL } = require("@/controllers/API/helpers/constants");
      const { getBaseUrl } = require("../utils/custom-code-samples");
      expect(config.BASENAME).toBe(prefix);
      expect(getURL("LOGIN")).toBe(`${prefix}/api/v1/login`);
      expect(config.BASE_URL_API_V2).toBe(`${prefix}/api/v2/`);
      expect(config.HEALTH_CHECK_URL).toBe(`${prefix}/health_check`);
      const { applyBasePath } = require("../utils/urls");
      expect(applyBasePath("/api/v1/build/flow-1/node-1/stream")).toBe(
        `${prefix}/api/v1/build/flow-1/node-1/stream`,
      );
      expect(applyBasePath(`${prefix}/api/v1/build/flow-1/node-1/stream`)).toBe(
        `${prefix}/api/v1/build/flow-1/node-1/stream`,
      );
      expect(applyBasePath("https://example.com/api/v1/run")).toBe(
        "https://example.com/api/v1/run",
      );
      expect(applyBasePath("//example.com/api/v1/run")).toBe(
        "//example.com/api/v1/run",
      );
      expect(getBaseUrl()).toBe(`${window.location.origin}${prefix}`);
      const { customA2aPublishOrigin } = require("../utils/custom-a2a-address");
      const {
        suggestedCallbackUrl,
      } = require("@/pages/SettingsPage/pages/ConnectionsPage/helpers/setup-guide");
      expect(customA2aPublishOrigin()).toBe(
        `${window.location.origin}${prefix}`,
      );
      expect(suggestedCallbackUrl("google", "https://example.com")).toBe(
        `https://example.com${prefix}/api/v1/connections/oauth/google/callback`,
      );
      const {
        getNewJsApiCode,
      } = require("@/modals/apiModal/utils/get-js-api-code");
      const code = getNewJsApiCode({
        flowId: "flow-1",
        endpointName: "",
        processedPayload: {
          tweaks: {
            chat: { files: "image.png" },
            file: { path: ["document.pdf"] },
          },
        },
        shouldDisplayApiKey: true,
      });
      expect(code).toContain(`path: \`${prefix}/api/v1/files/upload/`);
      expect(code).toContain(`path: '${prefix}/api/v2/files'`);
      expect(code).toContain(`path: \`${prefix}/api/v1/run/flow-1\``);
    },
  );
});

describe("base path validation", () => {
  it.each([
    ["", ""],
    ["/", ""],
    ["langflow", "/langflow"],
    ["/tools/langflow/", "/tools/langflow"],
    [" /tools/v1.13/ ", "/tools/v1.13"],
  ])("normalizes %s", (value, expected) => {
    expect(normalizeBasePath(value)).toBe(expected);
  });

  it.each([
    "https://example.com",
    "//example.com",
    "/a//b",
    "/a/../b",
    "/a/./b",
    "/a?b",
    "/a#b",
    "/a\\b",
    "/a%2fb",
    "/a b",
  ])("rejects a prefix that is not a plain URL path %s", (value) => {
    expect(() => normalizeBasePath(value)).toThrow("frontend base path");
  });
});
