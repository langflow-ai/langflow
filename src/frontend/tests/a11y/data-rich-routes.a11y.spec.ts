import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

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

async function waitForNetworkToSettle(page: LangflowPage) {
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

async function openRoute(page: LangflowPage, path: string) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto(path);
  await disableAnimations(page);
  await expect(page).toHaveURL(new RegExp(`${path}/?$`), {
    timeout: TIMEOUTS.standard,
  });
}

test.describe("data-rich route accessibility", () => {
  test(
    "scans MCP tab with published actions",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.route("**/api/v1/mcp/project/**", async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith("/installed")) {
          await route.fulfill({
            json: [
              { name: "cursor", installed: true, available: true },
              { name: "claude", installed: false, available: true },
            ],
          });
          return;
        }

        await route.fulfill({
          json: {
            auth_settings: { auth_type: "none" },
            tools: [
              {
                id: "a11y-mcp-action-1",
                name: "Research Assistant",
                description: "Summarize source material",
                action_name: "research_assistant",
                action_description: "Summarize source material",
                mcp_enabled: true,
              },
              {
                id: "a11y-mcp-action-2",
                name: "Lead Enrichment",
                description: "Find company context",
                action_name: "lead_enrichment",
                action_description: "Find company context",
                mcp_enabled: false,
              },
            ],
          },
        });
      });

      await openRoute(page, "/mcp");
      await expect(page.getByTestId("mcp-server-title")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("research_assistant")).toBeVisible();
      await waitForNetworkToSettle(page);

      await page.runA11yScan("mcp-data-rich");
    },
  );

  // NOTE: the files page (/assets/files) has dedicated, full-state coverage in
  // files.a11y.spec.ts (populated / empty / mobile / selected / actions menu /
  // delete modal / rename editing + keyboard operability).

  test(
    "scans MCP servers page with configured servers",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.route("**/api/v2/mcp/servers?**", async (route) => {
        await route.fulfill({
          json: [
            {
              id: "a11y-mcp-1",
              name: "docs-search",
              description: "Search documentation",
              mode: "stdio",
              toolsCount: 4,
              error: null,
            },
            {
              id: "a11y-mcp-2",
              name: "analytics",
              description: "Analytics tools",
              mode: "streamable-http",
              toolsCount: 0,
              error: null,
            },
          ],
        });
      });

      await openRoute(page, "/settings/mcp-servers");
      await expect(page.getByTestId("mcp_server_name_0")).toHaveText(
        "docs-search",
        { timeout: TIMEOUTS.standard },
      );
      await expect(page.getByTestId("mcp_server_name_1")).toHaveText(
        "analytics",
      );
      await waitForNetworkToSettle(page);

      await page.runA11yScan("settings-mcp-servers-data-rich");
    },
  );
});
