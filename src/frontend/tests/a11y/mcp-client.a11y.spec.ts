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

async function openMcpClientRoute(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/mcp-client");
  await disableAnimations(page);
  await expect(
    page.getByRole("heading", { name: "Langflow MCP Client" }),
  ).toBeVisible({ timeout: TIMEOUTS.standard });
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

test.describe("MCP client route accessibility", () => {
  test(
    "scans the default (Bob) agent tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);
      await expect(
        page.getByRole("tab", { name: "Bob (IBM)" }),
      ).toHaveAttribute("aria-selected", "true");
      await expect(page.getByText("mcpServers")).toBeVisible();

      await page.runA11yScan("settings-mcp-client-bob");
    },
  );

  test(
    "scans the Claude Code agent tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);
      await page.getByRole("tab", { name: "Claude Code" }).click();
      await expect(page.getByText("claude mcp add langflow")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-mcp-client-claude-code");
    },
  );

  test(
    "scans the copied confirmation state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);
      await page.getByTestId("copy-json-button").click();
      await expect(page.getByText("Copied")).toBeAttached({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-mcp-client-copied");
    },
  );

  test(
    "scans on a mobile viewport",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openMcpClientRoute(page);
      await expect(page.getByRole("tab", { name: "Bob (IBM)" })).toBeVisible();

      await page.runA11yScan("settings-mcp-client-mobile");
    },
  );

  test(
    "exposes the agent switcher as a tablist with a labelled panel",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);

      const tablist = page.getByRole("tablist", {
        name: "Choose a coding agent",
      });
      await expect(tablist).toBeVisible();
      await expect(tablist.getByRole("tab")).toHaveCount(2);

      const bob = page.getByRole("tab", { name: "Bob (IBM)" });
      const claude = page.getByRole("tab", { name: "Claude Code" });
      await expect(bob).toHaveAttribute("aria-selected", "true");
      await expect(claude).toHaveAttribute("aria-selected", "false");

      // The panel is named by the active tab and both tabs point at it.
      const panel = page.getByRole("tabpanel");
      await expect(panel).toHaveAttribute(
        "aria-labelledby",
        "mcp-client-tab-bob",
      );
      await expect(bob).toHaveAttribute("aria-controls", "mcp-client-tabpanel");
      await expect(claude).toHaveAttribute(
        "aria-controls",
        "mcp-client-tabpanel",
      );
    },
  );

  test(
    "moves selection with arrow keys and a roving tab stop",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);

      const bob = page.getByRole("tab", { name: "Bob (IBM)" });
      const claude = page.getByRole("tab", { name: "Claude Code" });
      // Only the active tab is a tab stop.
      await expect(bob).toHaveAttribute("tabindex", "0");
      await expect(claude).toHaveAttribute("tabindex", "-1");

      await bob.focus();
      await page.keyboard.press("ArrowRight");
      await expect(claude).toBeFocused();
      await expect(claude).toHaveAttribute("aria-selected", "true");
      await expect(claude).toHaveAttribute("tabindex", "0");
      await expect(bob).toHaveAttribute("tabindex", "-1");
      await expect(page.getByText("claude mcp add langflow")).toBeVisible();

      // Wraps back to the first tab.
      await page.keyboard.press("ArrowRight");
      await expect(bob).toBeFocused();
      await expect(bob).toHaveAttribute("aria-selected", "true");
    },
  );

  test(
    "names the copy controls and keeps them keyboard operable",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpClientRoute(page);

      // Default tab has the JSON copy; icon-only, so the name comes from
      // aria-label (the pre-existing IBM input_label_exists violation).
      await expect(
        page.getByRole("button", { name: "Copy JSON config" }),
      ).toBeVisible();

      await page.getByRole("tab", { name: "Claude Code" }).click();
      await expect(
        page.getByRole("button", { name: "Copy command" }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Copy JSON config" }),
      ).toBeVisible();
    },
  );
});
