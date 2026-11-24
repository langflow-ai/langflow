// The scroll workaround must run wherever WebKit does, not only where the
// user agent happens to say "Safari".
//
// An embedded WKWebView (Tauri, and other native shells) reports
//   Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)
// with no "Safari/" token, so the previous /safari/ sniff was false there. The
// Playground then ran without the workaround in a WebKit runtime, while Safari
// itself received it — the scroll jumped back to the top of a reply as soon as
// streaming finished.

// ESM-only package; these assertions never reach the hook (the component
// returns before using it, or is asserted as an unrendered element), so a stub
// keeps the suite out of the jest ESM transform allowlist.
jest.mock("use-stick-to-bottom", () => ({
  useStickToBottomContext: () => ({
    scrollRef: { current: null },
    stopScroll: () => {},
  }),
}));

const TAURI_WKWEBVIEW =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)";
const SAFARI =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15";
const CHROME =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const EDGE_WEBVIEW2 =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0";
const ANDROID_WEBVIEW =
  "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/141.0.0.0 Mobile Safari/537.36";
const FIREFOX =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0";

const originalUserAgent = navigator.userAgent;

const setUserAgent = (userAgent: string) => {
  Object.defineProperty(navigator, "userAgent", {
    value: userAgent,
    configurable: true,
  });
};

const loadModule = () => {
  let loaded: typeof import("../safari-scroll-fix");
  jest.isolateModules(() => {
    loaded = require("../safari-scroll-fix");
  });
  return loaded!;
};

describe("safari-scroll-fix WebKit detection", () => {
  afterEach(() => {
    setUserAgent(originalUserAgent);
  });

  describe("engine predicate", () => {
    it.each([
      ["an embedded WKWebView", TAURI_WKWEBVIEW, true],
      ["Safari", SAFARI, true],
      ["Chrome", CHROME, false],
      ["Edge / WebView2", EDGE_WEBVIEW2, false],
      ["Android WebView", ANDROID_WEBVIEW, false],
      ["Firefox", FIREFOX, false],
    ])(
      "should_report_%s_correctly_when_matching_the_engine",
      (_label, userAgent, expected) => {
        const { isWebKitEngine } = loadModule();

        expect(isWebKitEngine(userAgent as string)).toBe(expected);
      },
    );
  });

  describe("component gating", () => {
    it("should_mount_the_workaround_when_running_in_an_embedded_webkit_view", () => {
      setUserAgent(TAURI_WKWEBVIEW);
      const { SafariScrollFix } = loadModule();

      expect(SafariScrollFix()).not.toBeNull();
    });

    it("should_not_mount_the_workaround_when_running_in_chromium", () => {
      setUserAgent(CHROME);
      const { SafariScrollFix } = loadModule();

      expect(SafariScrollFix()).toBeNull();
    });
  });
});
