import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type ServerRow = {
  name: string;
  mode: string | null;
  toolsCount: number | null;
  error?: string;
};

const populatedServers: ServerRow[] = [
  { name: "filesystem", mode: "STDIO", toolsCount: 12 },
  { name: "single-tool-server", mode: "STDIO", toolsCount: 1 },
  { name: "empty-server", mode: "HTTP", toolsCount: 0 },
];

const erroredServers: ServerRow[] = [
  {
    name: "timeout-server",
    mode: "STDIO",
    toolsCount: null,
    error: "Timeout while connecting to server",
  },
  {
    name: "broken-server",
    mode: "HTTP",
    toolsCount: null,
    error: "Connection refused by remote host",
  },
  { name: "filesystem", mode: "STDIO", toolsCount: 12 },
];

// toolsCount === null with no error renders the "Loading..." status.
const loadingServers: ServerRow[] = [
  { name: "pending-server", mode: null, toolsCount: null },
];

const stdioServerDetail = {
  name: "filesystem",
  command: "npx",
  args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
  env: { HOME: "/root" },
};

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

/**
 * The page lists servers from GET /api/v2/mcp/servers. It is fetched twice:
 * `action_count=false` first (fast), then `action_count=true` to fill in
 * mode/toolsCount. Both must resolve to the same rows or the merge in
 * `useGetMCPServers` flips counts back to null mid-scan.
 */
async function mockServers(page: LangflowPage, servers: ServerRow[]) {
  await page.route(/\/api\/v2\/mcp\/servers(\?.*)?$/, async (route: Route) => {
    const method = route.request().method();

    if (method === "GET") {
      await route.fulfill({ json: servers });
      return;
    }

    if (method === "DELETE") {
      await route.fulfill({ json: { message: "Server deleted" } });
      return;
    }

    await route.continue();
  });
}

async function mockServerDetail(page: LangflowPage) {
  await page.route(
    /\/api\/v2\/mcp\/servers\/[^/?]+(\?.*)?$/,
    async (route: Route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: stdioServerDetail });
        return;
      }
      await route.continue();
    },
  );
}

async function openMcpServersRoute(
  page: LangflowPage,
  servers = populatedServers,
) {
  await mockServerDetail(page);
  await mockServers(page, servers);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/mcp-servers");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toContainText(
    "MCP Servers",
    { timeout: TIMEOUTS.standard },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

async function focusedTestId(page: LangflowPage) {
  return page.evaluate(
    () => document.activeElement?.getAttribute("data-testid") ?? "",
  );
}

async function openActionsMenu(page: LangflowPage, serverName: string) {
  await page.getByTestId(`mcp-server-menu-button-${serverName}`).click();
  await expect(page.getByRole("menu")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

test.describe("MCP servers route accessibility", () => {
  test(
    "scans populated server list",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await expect(page.getByTestId("mcp_server_name_0")).toHaveText(
        "filesystem",
      );
      await expect(page.getByText("12 tools")).toBeVisible();
      await expect(page.getByText("1 tool", { exact: true })).toBeVisible();
      await expect(page.getByText("No tools found")).toBeVisible();
      await expect(page.getByText("Added MCP Servers")).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-populated");
    },
  );

  test(
    "scans empty server list",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page, []);
      await expect(page.getByText("No MCP servers added")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("Added MCP Servers")).toHaveCount(0);

      await page.runA11yScan("settings-mcp-servers-empty");
    },
  );

  test(
    "scans server list with connection errors",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page, erroredServers);
      await expect(page.getByText("Timeout", { exact: true })).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("Error", { exact: true })).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-error-status");
    },
  );

  test(
    "scans server list in loading status",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page, loadingServers);
      await expect(page.getByText("Loading...")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-mcp-servers-loading-status");
    },
  );

  test(
    "scans row actions menu open",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await openActionsMenu(page, "filesystem");
      await expect(page.getByRole("menuitem", { name: "Edit" })).toBeVisible();
      await expect(
        page.getByRole("menuitem", { name: "Delete" }),
      ).toBeVisible();

      // The portaled menu trips aria_content_in_landmark; that known Radix
      // debt is tracked in baselines/chromium__settings-mcp-servers-actions-menu.json.
      await page.runA11yScan("settings-mcp-servers-actions-menu");
    },
  );

  test(
    "scans add server modal on JSON tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByTestId("json-tab")).toBeVisible();
      await expect(page.getByText("Paste in JSON config")).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-add-modal-json");
    },
  );

  test(
    "scans add server modal on STDIO tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("stdio-tab").click();
      await expect(page.getByPlaceholder("Type server name...")).toBeVisible();
      await expect(page.getByPlaceholder("Type command...")).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-add-modal-stdio");
    },
  );

  test(
    "scans add server modal on HTTP tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("http-tab").click();
      await expect(
        page.getByPlaceholder("Streamable HTTP/SSE URL"),
      ).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-add-modal-http");
    },
  );

  test(
    "scans add server modal validation error",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("stdio-tab").click();
      await page.getByTestId("add-mcp-server-button").click();
      await expect(
        page.getByText("Name and command are required."),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await page.runA11yScan("settings-mcp-servers-add-modal-error");
    },
  );

  test(
    "scans edit server modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await openActionsMenu(page, "filesystem");
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("Update MCP Server")).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-edit-modal");
    },
  );

  test(
    "scans delete confirmation modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await openActionsMenu(page, "filesystem");
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(
        page.getByTestId("btn_delete_delete_confirmation_modal"),
      ).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-delete-modal");
    },
  );

  test(
    "scans populated list on a mobile viewport",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openMcpServersRoute(page);
      await expect(page.getByTestId("mcp_server_name_0")).toBeVisible();

      await page.runA11yScan("settings-mcp-servers-mobile");
    },
  );

  test(
    "names the add and edit dialogs by their visible title",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(
        page.getByRole("dialog", { name: "Add MCP Server" }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      // The generic BaseModal fallback title must not be what names the dialog.
      await expect(page.getByText("Dialog", { exact: true })).toHaveCount(0);

      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);

      await openActionsMenu(page, "filesystem");
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(
        page.getByRole("dialog", { name: "Update MCP Server" }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(page.getByText("Dialog", { exact: true })).toHaveCount(0);
    },
  );

  test(
    "labels every add-server field with its visible label",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: TIMEOUTS.standard });

      // JSON tab: the visible label must name the textarea, not the placeholder.
      await expect(
        dialog.getByRole("textbox", { name: "Paste in JSON config" }),
      ).toBeVisible();

      await page.getByTestId("stdio-tab").click();
      await expect(
        dialog.getByRole("textbox", { name: /^Name/ }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("textbox", { name: /^Command/ }),
      ).toBeVisible();
      // List-valued fields cannot use htmlFor, so they expose a named group.
      await expect(
        dialog.getByRole("group", { name: "Arguments" }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("group", { name: "Environment Variables" }),
      ).toBeVisible();

      await page.getByTestId("http-tab").click();
      await expect(
        dialog.getByRole("textbox", { name: /^Name/ }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("textbox", { name: /Streamable HTTP\/SSE URL/ }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("group", { name: "Headers" }),
      ).toBeVisible();
    },
  );

  test(
    "gives the list add/remove icon buttons accessible names",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.getByTestId("stdio-tab").click();

      await expect(
        dialog.getByRole("button", { name: "Add Argument" }),
      ).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: "Add row" }),
      ).toBeVisible();

      // A second argument row exposes the named remove control.
      await dialog.getByRole("button", { name: "Add Argument" }).click();
      await expect(
        dialog.getByRole("button", { name: "Remove item 1" }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
    },
  );

  test(
    "removing an argument row does not submit the form",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.getByTestId("stdio-tab").click();

      await dialog.getByRole("button", { name: "Add Argument" }).click();
      const removeButton = dialog.getByRole("button", {
        name: "Remove item 1",
      });
      await expect(removeButton).toBeVisible({ timeout: TIMEOUTS.standard });

      // The remove control defaulted to type=submit, so it submitted the modal
      // form and surfaced the "Name and command are required." error.
      await removeButton.click();
      await expect(dialog).toBeVisible();
      await expect(
        page.getByText("Name and command are required."),
      ).toHaveCount(0);
    },
  );

  test(
    "announces the add-server validation error",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("stdio-tab").click();
      await page.getByTestId("add-mcp-server-button").click();

      await expect(page.getByRole("alert")).toHaveText(
        "Name and command are required.",
        { timeout: TIMEOUTS.standard },
      );
    },
  );

  test(
    "exposes the server connection error to assistive tech",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page, erroredServers);
      // The detail otherwise lives only in a hover tooltip.
      await expect(
        page.getByText(
          "broken-server error: Connection refused by remote host",
        ),
      ).toBeAttached({ timeout: TIMEOUTS.standard });
    },
  );

  test(
    "opens the row actions menu by keyboard and restores focus on Escape",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      const trigger = page.getByTestId("mcp-server-menu-button-filesystem");
      await trigger.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("menu")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.keyboard.press("Escape");
      await expect(page.getByRole("menu")).toHaveCount(0);
      await expect
        .poll(
          async () =>
            page.evaluate(
              () => document.activeElement?.getAttribute("data-testid") ?? "",
            ),
          { timeout: TIMEOUTS.standard },
        )
        .toBe("mcp-server-menu-button-filesystem");
    },
  );

  test(
    "tabs through the page controls in visual order",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);

      // Start from the last sidebar link so the trace covers the page body
      // rather than the whole app chrome.
      await page.getByTestId("sidebar-nav-Messages").focus();

      const order: string[] = [];
      for (let i = 0; i < 4; i++) {
        await page.keyboard.press("Tab");
        order.push(await focusedTestId(page));
      }

      expect(order).toEqual([
        "add-mcp-server-button-page",
        "mcp-server-menu-button-filesystem",
        "mcp-server-menu-button-single-tool-server",
        "mcp-server-menu-button-empty-server",
      ]);
    },
  );

  test(
    "keeps Tab and Shift+Tab inside the add server modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Forward and backward must both stay within the dialog (WCAG 2.1.2).
      const inDialog = async () =>
        page.evaluate(
          () => !!document.activeElement?.closest('[role="dialog"]'),
        );
      for (let i = 0; i < 18; i++) {
        await page.keyboard.press("Tab");
        expect(
          await inDialog(),
          `forward tab ${i + 1} escaped the dialog`,
        ).toBe(true);
      }
      for (let i = 0; i < 12; i++) {
        await page.keyboard.press("Shift+Tab");
        // Radix parks focus on a body-level focus guard between wraps; only a
        // landing outside the dialog on a real element is a trap failure.
        const focused = await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null;
          if (!el || el === document.body) return "guard";
          return el.closest('[role="dialog"]') ? "in" : "out";
        });
        expect(focused, `backward tab ${i + 1} escaped the dialog`).not.toBe(
          "out",
        );
      }
    },
  );

  test(
    "orders the add modal tabs before the fields and footer",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // The tablist is visually first, so it must be the first stop.
      await page.keyboard.press("Tab");
      expect(await focusedTestId(page)).toBe("json-tab");

      await page.getByTestId("stdio-tab").click();
      const order: string[] = [];
      for (let i = 0; i < 11; i++) {
        await page.keyboard.press("Tab");
        const id = await focusedTestId(page);
        if (id) order.push(id);
      }
      // Tab leaves the tablist straight onto the first field: the panel itself
      // opts out of the tab order. Fields precede the footer actions, and the
      // ring closes back onto the tablist. Cancel/Close carry no test id.
      expect(order).toEqual([
        "stdio-name-input",
        "stdio-command-input",
        "input-list-plus-btn_-0",
        "stdio-args_0",
        "stdio-env-key-0",
        "stdio-env-value-0",
        "stdio-env-plus-btn-0",
        "add-mcp-server-button",
        "stdio-tab",
      ]);
    },
  );

  test(
    "never focuses an inactive tab panel",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("stdio-tab").click();

      // Radix hides inactive panels with the `hidden` attribute only. A display
      // utility on TabsContent used to outrank it, leaving zero-height panels
      // that still took focus and painted a stray ring (WCAG 2.4.3 / 4.1.2).
      const inactiveDisplays = await page.evaluate(() =>
        Array.from(
          document.querySelectorAll('[role="tabpanel"][data-state="inactive"]'),
        ).map((el) => getComputedStyle(el as HTMLElement).display),
      );
      expect(inactiveDisplays.length).toBeGreaterThan(0);
      expect(inactiveDisplays.every((d) => d === "none")).toBe(true);

      const strayStops: string[] = [];
      for (let i = 0; i < 14; i++) {
        await page.keyboard.press("Tab");
        const stray = await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null;
          const panel = el?.closest('[role="tabpanel"]');
          return panel?.getAttribute("data-state") === "inactive"
            ? panel.id
            : null;
        });
        if (stray) strayStops.push(stray);
      }
      expect(strayStops).toEqual([]);

      // Panels hold their own focusable fields, so none of them is a tab stop
      // (matches GlobalVariableModal).
      const panelTabIndexes = await page.evaluate(() =>
        Array.from(document.querySelectorAll('[role="tabpanel"]')).map(
          (el) => (el as HTMLElement).tabIndex,
        ),
      );
      expect(panelTabIndexes.every((t) => t === -1)).toBe(true);
    },
  );

  test(
    "keeps disabled type tabs out of the edit modal tab order",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await openActionsMenu(page, "filesystem");
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Editing locks the server type: the other two tabs are disabled and must
      // not be tab stops, while the active one stays reachable (WCAG 2.1.1).
      await expect(page.getByTestId("json-tab")).toBeDisabled();
      await expect(page.getByTestId("http-tab")).toBeDisabled();
      await expect(page.getByTestId("stdio-tab")).toBeEnabled();

      await page.keyboard.press("Tab");
      expect(await focusedTestId(page)).toBe("stdio-tab");
    },
  );

  test(
    "labels the header value option control in English",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      await page.getByTestId("add-mcp-server-button-page").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.getByTestId("http-tab").click();

      // en.json was missing this key, so i18next rendered the raw key as the
      // button's accessible name.
      await expect(
        page.getByRole("button", { name: "input.selectOption" }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Select input option" }).first(),
      ).toBeVisible();
    },
  );

  test(
    "announces the pending server load as a status region",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      // Hold the list request open so the page stays in its loading state.
      let release: () => void = () => {};
      const pending = new Promise<void>((resolve) => {
        release = resolve;
      });
      await page.route(
        /\/api\/v2\/mcp\/servers(\?.*)?$/,
        async (route: Route) => {
          await pending;
          await route.fulfill({ json: populatedServers });
        },
      );
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/mcp-servers");

      // The spinner itself is aria-hidden, so the region must carry the text.
      const loadingRegion = page.getByTestId("mcp-servers-loading");
      await expect(loadingRegion).toHaveText("Loading MCP servers", {
        timeout: TIMEOUTS.standard,
      });
      await expect(loadingRegion).toHaveRole("status");

      await page.runA11yScan("settings-mcp-servers-loading-region");

      release();
      await expect(page.getByTestId("mcp_server_name_0")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(loadingRegion).toHaveCount(0);
    },
  );

  test(
    "exposes the server list with list semantics",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMcpServersRoute(page);
      const list = page.getByRole("list", { name: "Added MCP Servers" });
      await expect(list).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(list.getByRole("listitem")).toHaveCount(
        populatedServers.length,
      );
    },
  );
});
