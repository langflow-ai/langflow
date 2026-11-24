const cookieNames = [
  "access_token_lf",
  "refresh_token_lf",
  "apikey_tkn_lflw",
  "auto_login_lf",
];

function instance(prefix: string) {
  document.querySelector("base")?.remove();
  const base = document.createElement("base");
  base.setAttribute("href", `${prefix}/`);
  document.head.appendChild(base);
  window.history.replaceState(null, "", `${prefix}/login`);
  jest.resetModules();
  const constants = require("@/constants/constants");
  return {
    manager: require("../cookie-manager")
      .cookieManager as typeof import("../cookie-manager").cookieManager,
    names: [
      constants.LANGFLOW_ACCESS_TOKEN,
      constants.LANGFLOW_REFRESH_TOKEN,
      constants.LANGFLOW_API_TOKEN,
      constants.LANGFLOW_AUTO_LOGIN_OPTION,
    ] as string[],
  };
}

afterEach(() => {
  for (const path of ["/", "/langflow-a/", "/tools/langflow-b/"]) {
    for (const name of cookieNames) {
      document.cookie = `${name}=; Max-Age=0; Path=${path}`;
      const suffix =
        path === "/" ? "" : `_${encodeURIComponent(path.slice(0, -1))}`;
      document.cookie = `${name}${suffix}=; Max-Age=0; Path=${path}`;
    }
  }
  document.querySelector("base")?.remove();
  window.history.replaceState(null, "", "/");
  jest.resetModules();
});

it("keeps sibling instances' cookies through login and logout", () => {
  const first = instance("/langflow-a");
  for (const name of first.names) first.manager.set(name, "first");

  const second = instance("/tools/langflow-b");
  for (const name of second.names) {
    expect(second.manager.get(name)).toBeUndefined();
    second.manager.set(name, "second");
  }

  window.history.replaceState(null, "", "/langflow-a/flow/example");
  for (const name of first.names) expect(first.manager.get(name)).toBe("first");
  first.manager.clearAuthCookies();
  expect(document.cookie).toBe("");

  window.history.replaceState(null, "", "/tools/langflow-b/settings");
  for (const name of second.names)
    expect(second.manager.get(name)).toBe("second");
  second.manager.clearAuthCookies();
  expect(document.cookie).toBe("");
});

it.each(["", "/langflow-a", "/tools/langflow-b"])(
  "uses the same path for the auth cookie helper at %s",
  (prefix) => {
    const { manager, names } = instance(prefix);
    const { setAuthCookie } = require("../utils");
    setAuthCookie(manager.getCookies(), names[3], "auto");
    expect(manager.get(names[3])).toBe("auto");
    if (prefix) {
      window.history.replaceState(null, "", "/");
      expect(document.cookie).toBe("");
      window.history.replaceState(null, "", `${prefix}/login`);
    }
    manager.clearAuthCookies();
    expect(document.cookie).toBe("");
  },
);

it("ignores legacy root cookies and preserves them through logout", () => {
  const root = instance("");
  for (const name of root.names) root.manager.set(name, "root");
  const prefixed = instance("/langflow-a");
  expect(prefixed.names).toEqual([
    "access_token_lf_%2Flangflow-a",
    "refresh_token_lf_%2Flangflow-a",
    "apikey_tkn_lflw_%2Flangflow-a",
    "auto_login_lf_%2Flangflow-a",
  ]);
  for (const name of prefixed.names) {
    expect(prefixed.manager.get(name)).toBeUndefined();
    prefixed.manager.set(name, "prefixed");
    expect(prefixed.manager.get(name)).toBe("prefixed");
  }
  prefixed.manager.clearAuthCookies();
  for (const name of prefixed.names)
    expect(prefixed.manager.get(name)).toBeUndefined();
  for (const name of root.names) expect(root.manager.get(name)).toBe("root");
});
