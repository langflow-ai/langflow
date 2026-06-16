// Structural tests for routes.tsx — pins the routing decisions the landing
// page introduced: exact "/" is a public index route (outside ProtectedRoute),
// the protected tree no longer claims "/" via an index→flows redirect, and the
// auth/lothal routes are still mounted. Page modules are stubbed: the router's
// shape is the unit under test, not the pages.

import type { ReactNode } from "react";

jest.mock("@/contexts", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/customization/components/custom-DashboardWrapperPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/customization/utils/custom-routes-store", () => ({
  CustomRoutesStore: () => null,
}));
jest.mock("@/customization/utils/custom-routes-store-pages", () => ({
  CustomRoutesStorePages: () => null,
}));
jest.mock("@/components/authorization/authAdminGuard", () => ({
  ProtectedAdminRoute: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/components/authorization/authGuard", () => ({
  ProtectedRoute: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/components/authorization/authLangflowGuard", () => ({
  ProtectedLangflowRoute: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/components/authorization/authLoginGuard", () => ({
  ProtectedLoginRoute: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/components/authorization/authSettingsGuard", () => ({
  AuthSettingsGuard: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/components/authorization/playgroundAuthGate", () => ({
  PlaygroundAuthGate: ({ children }: { children?: ReactNode }) => children,
}));
jest.mock("@/pages/AppAuthenticatedPage", () => ({
  AppAuthenticatedPage: () => null,
}));
jest.mock("@/pages/AppInitPage", () => ({ AppInitPage: () => null }));
jest.mock("@/pages/AppWrapperPage", () => ({ AppWrapperPage: () => null }));
jest.mock("@/pages/FlowPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/LoginPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/MainPage/pages/filesPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/MainPage/pages/homePage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/MainPage/pages/knowledgePage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock(
  "@/pages/MainPage/pages/knowledgePage/sourceChunksPage/SourceChunksPage",
  () => ({ __esModule: true, default: () => null }),
);
jest.mock("@/pages/MainPage/pages/main-page", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/ApiKeysPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/GeneralPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/GlobalVariablesPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/MCPServersPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/McpClientPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/ModelProvidersPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/messagesPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/SettingsPage/pages/ShortcutsPage", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/ViewPage", () => ({
  __esModule: true,
  default: () => null,
}));

import router from "../routes";

type RouteNode = {
  path?: string;
  index?: boolean;
  children?: RouteNode[];
};

// Depth-first collection of every node so assertions don't depend on nesting
// details that are free to change.
function flatten(nodes: RouteNode[]): RouteNode[] {
  return nodes.flatMap((n) => [n, ...flatten(n.children ?? [])]);
}

const routes = router.routes as RouteNode[];
const all = flatten(routes);

// The app shell chain: root → AppInitPage ("") → AppWrapperPage ("").
const root = routes.find((r) => r.path === "/" || r.path === "/:customParam?");
const appInit = root?.children?.[0];
const appWrapper = appInit?.children?.[0];

describe("routes.tsx topology", () => {
  it("mounts a public index route (the landing page) directly under the app wrapper", () => {
    expect(appWrapper).toBeDefined();
    const first = appWrapper?.children?.[0];
    // The landing must be the index — and a leaf, not the protected subtree.
    expect(first?.index).toBe(true);
    expect(first?.children).toBeUndefined();
  });

  it("keeps login/signup/admin-login as siblings of the protected tree (still public)", () => {
    const paths = (appWrapper?.children ?? []).map((c) => c.path);
    expect(paths).toEqual(
      expect.arrayContaining(["login", "signup", "login/admin"]),
    );
  });

  it("no longer claims exact '/' inside the protected tree (the old index→flows redirect is gone)", () => {
    // An index route matches exact "/" only when every ancestor is pathless.
    // (Deeper index routes — e.g. settings → general — match their own path
    // and are fine.) After the change, the landing must be the only one.
    const rootClaimers = (nodes: RouteNode[]): RouteNode[] =>
      nodes.flatMap((n) => {
        if (n.index) return [n];
        if (!n.path || n.path === "") return rootClaimers(n.children ?? []);
        return [];
      });
    const claimers = rootClaimers(appWrapper?.children ?? []);
    expect(claimers).toHaveLength(1);
    expect(claimers[0]).toBe(appWrapper?.children?.[0]);
  });

  it("still mounts the flows app and the lothal pages", () => {
    const paths = all.map((r) => r.path);
    expect(paths).toEqual(
      expect.arrayContaining([
        "flows/",
        "lothal",
        "lothal/:projectId",
        "lothal/design-system",
      ]),
    );
  });

  it("keeps the catch-all redirect under the root route", () => {
    const children = root?.children ?? [];
    expect(children[children.length - 1]?.path).toBe("*");
  });
});
