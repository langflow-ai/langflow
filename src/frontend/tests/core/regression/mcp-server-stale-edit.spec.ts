import type { APIRequestContext } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { useMcpServerListWithoutToolCounts } from "../../utils/mcp-server-list-without-tool-counts";

/**
 * A server deleted elsewhere (another tab, pod, or teammate) can still be
 * listed on a stale settings page. Editing it must report that it is gone and
 * must never re-create it with only the fields the edit form happened to send.
 */
const SERVER_CONFIG = {
  url: "http://real.example.com/mcp",
  headers: { "X-Key": "abc" },
};

const serverPath = (name: string) => `/api/v2/mcp/servers/${name}`;

async function createServer(request: APIRequestContext, name: string) {
  const response = await request.post(serverPath(name), {
    data: SERVER_CONFIG,
  });
  expect(response.status()).toBe(200);
}

async function deleteServer(request: APIRequestContext, name: string) {
  const response = await request.delete(serverPath(name));
  expect(response.status()).toBe(200);
}

async function expectServerGone(request: APIRequestContext, name: string) {
  expect((await request.get(serverPath(name))).status()).toBe(404);
  const list = await request.get("/api/v2/mcp/servers?action_count=false");
  const names = ((await list.json()) as { name: string }[]).map(
    (server) => server.name,
  );
  expect(names).not.toContain(name);
}

async function openServersPageListing(
  page: Parameters<typeof awaitBootstrapTest>[0],
  name: string,
) {
  await useMcpServerListWithoutToolCounts(page);
  await awaitBootstrapTest(page, { skipModal: true, seedFlowIfEmpty: false });
  await createServer(page.request, name);
  await page.goto("/settings/mcp-servers");
  await expect(page.getByTestId(`mcp-server-menu-button-${name}`)).toBeVisible({
    timeout: 30_000,
  });
}

async function clickEdit(
  page: Parameters<typeof awaitBootstrapTest>[0],
  name: string,
) {
  await page.getByTestId(`mcp-server-menu-button-${name}`).click();
  await page.getByRole("menuitem", { name: "Edit" }).click();
}

test(
  "editing a server deleted elsewhere reports it is gone instead of opening an empty form",
  { tag: ["@release", "@mcp"] },
  async ({ page }) => {
    const name = `stale-edit-${Date.now()}`;
    await openServersPageListing(page, name);

    await deleteServer(page.request, name);
    await clickEdit(page, name);

    await expect(
      page.getByText("This MCP server no longer exists", { exact: false }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("add-mcp-server-button")).toHaveCount(0);
    await expect(
      page.getByTestId(`mcp-server-menu-button-${name}`),
    ).toHaveCount(0, { timeout: 10_000 });
    await expectServerGone(page.request, name);
  },
);

test(
  "saving an edit after the server was deleted does not re-create it",
  { tag: ["@release", "@mcp"] },
  async ({ page }) => {
    const name = `stale-save-${Date.now()}`;
    await openServersPageListing(page, name);

    await clickEdit(page, name);
    const saveButton = page.getByTestId("add-mcp-server-button");
    await expect(saveButton).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("http-url-input")).toHaveValue(
      SERVER_CONFIG.url,
    );

    await deleteServer(page.request, name);
    await saveButton.click();

    await expect(
      page.getByText("This MCP server no longer exists", { exact: false }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByTestId(`mcp-server-menu-button-${name}`),
    ).toHaveCount(0, { timeout: 10_000 });
    await expectServerGone(page.request, name);
  },
);
