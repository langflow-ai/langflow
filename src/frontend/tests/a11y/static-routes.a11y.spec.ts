import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { AriaRole } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type StaticRoute = {
  id: string;
  path: string;
  requiresMainContent?: boolean;
  ready?: ReadyCheck[];
};

type ReadyCheck = {
  testId?: string;
  containsText?: string;
  role?: string;
  name?: string;
  first?: boolean;
  oneOf?: ReadyCheck[];
};

type RouteManifest = {
  static: StaticRoute[];
};

function resolveRouteManifestPath() {
  const candidates = [
    path.resolve(process.cwd(), "../../scripts/a11y/a11y_routes.json"),
    path.resolve(process.cwd(), "scripts/a11y/a11y_routes.json"),
  ];
  const manifestPath = candidates.find((candidate) => existsSync(candidate));
  if (!manifestPath) {
    throw new Error(
      `Could not find scripts/a11y/a11y_routes.json from ${process.cwd()}`,
    );
  }
  return manifestPath;
}

const routeManifestPath = resolveRouteManifestPath();
const routeManifest = JSON.parse(
  readFileSync(routeManifestPath, "utf8"),
) as RouteManifest;
const canonicalStaticRoutes = routeManifest.static;

function namePattern(name: string) {
  return new RegExp(name, "i");
}

function locatorForReadyCheck(page: LangflowPage, check: ReadyCheck) {
  if (check.testId) {
    return page.getByTestId(check.testId);
  }
  if (check.role) {
    const locator = page.getByRole(check.role as AriaRole, {
      name: check.name ? namePattern(check.name) : undefined,
    });
    return check.first ? locator.first() : locator;
  }
  throw new Error(
    `Unsupported a11y route ready check: ${JSON.stringify(check)}`,
  );
}

async function expectReadyCheck(page: LangflowPage, check: ReadyCheck) {
  if (check.oneOf) {
    const locator = check.oneOf
      .map((candidate) => locatorForReadyCheck(page, candidate))
      .reduce((combined, candidate) => combined.or(candidate));
    // A oneOf check passes when at least one candidate renders. Multiple can
    // match (e.g. the KB page shows both the "Add knowledge" button and the
    // search input), so scope to .first() to avoid a strict-mode violation.
    await expect(locator.first()).toBeVisible({ timeout: TIMEOUTS.standard });
    return;
  }

  const locator = locatorForReadyCheck(page, check);
  if (check.containsText) {
    await expect(locator).toContainText(check.containsText, {
      timeout: TIMEOUTS.standard,
    });
    return;
  }
  await expect(locator).toBeVisible({ timeout: TIMEOUTS.standard });
}

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function waitForRouteToSettle(page: LangflowPage, route: StaticRoute) {
  if (route.requiresMainContent) {
    await awaitBootstrapTest(page, { skipModal: true });
  }

  await page.goto(route.path);
  await disableAnimations(page);
  await expect(page).toHaveURL(new RegExp(`${route.path}/?$`), {
    timeout: TIMEOUTS.standard,
  });
  for (const readyCheck of route.ready ?? []) {
    await expectReadyCheck(page, readyCheck);
  }
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

test.describe("canonical static route accessibility", () => {
  for (const route of canonicalStaticRoutes) {
    test(
      `scans ${route.path}`,
      { tag: ["@release", "@workspace"] },
      async ({ page }) => {
        await waitForRouteToSettle(page, route);
        await page.runA11yScan(`route-${route.id}`);
      },
    );
  }
});
