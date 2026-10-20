const cookieNames = [
  "access_token_lf",
  "refresh_token_lf",
  "apikey_tkn_lflw",
  "auto_login_lf",
];

function instance(
  prefix: string,
): typeof import("../cookie-manager").cookieManager {
  document.querySelector("base")?.remove();
  const base = document.createElement("base");
  base.setAttribute("href", `${prefix}/`);
  document.head.appendChild(base);
  window.history.replaceState(null, "", `${prefix}/login`);
  jest.resetModules();
  return require("../cookie-manager").cookieManager;
}

afterEach(() => {
  for (const path of ["/", "/langflow-a/", "/tools/langflow-b/"]) {
    for (const name of cookieNames) {
      document.cookie = `${name}=; Max-Age=0; Path=${path}`;
    }
  }
  document.querySelector("base")?.remove();
  window.history.replaceState(null, "", "/");
  jest.resetModules();
});

it("keeps sibling instances' cookies through login and logout", () => {
  const first = instance("/langflow-a");
  for (const name of cookieNames) first.set(name, "first");

  const second = instance("/tools/langflow-b");
  for (const name of cookieNames) {
    expect(second.get(name)).toBeUndefined();
    second.set(name, "second");
  }

  window.history.replaceState(null, "", "/langflow-a/flow/example");
  for (const name of cookieNames) expect(first.get(name)).toBe("first");
  first.clearAuthCookies();
  expect(document.cookie).toBe("");

  window.history.replaceState(null, "", "/tools/langflow-b/settings");
  for (const name of cookieNames) expect(second.get(name)).toBe("second");
  second.clearAuthCookies();
  expect(document.cookie).toBe("");
});

it.each(["", "/langflow-a", "/tools/langflow-b"])(
  "uses the same path for the auth cookie helper at %s",
  (prefix) => {
    const manager = instance(prefix);
    const { setAuthCookie } = require("../utils");
    setAuthCookie(manager.getCookies(), "auto_login_lf", "auto");
    expect(manager.get("auto_login_lf")).toBe("auto");
    if (prefix) {
      window.history.replaceState(null, "", "/");
      expect(document.cookie).toBe("");
      window.history.replaceState(null, "", `${prefix}/login`);
    }
    manager.clearAuthCookies();
    expect(document.cookie).toBe("");
  },
);
