import { readFileSync } from "node:fs";
import type {
  APIResponse,
  Browser,
  BrowserContext,
  Locator,
  Page,
  Response as PlaywrightResponse,
  Route,
} from "@playwright/test";
import type {
  AuthorizationCapabilities,
  AuthorizationTeam,
} from "../../../../src/types/authz";
import { expect, test } from "../../../fixtures";
import { createActiveUserViaApi } from "../../../utils/auth/manage-users-via-api";
import {
  AUTHZ_STARTUP_LOG,
  assertAuthzStartup,
} from "../../../utils/authz-e2e-mode.mjs";
import { TEXTS } from "../../../utils/constants/texts";
import { TIMEOUTS } from "../../../utils/constants/timeouts";
import {
  populateTextInputOutputFlow,
  runTextInputOutputFlow,
} from "../../../utils/flow/text-input-output-flow";
import {
  type FlowData,
  flushPendingFlowAutosave,
} from "../../../utils/flow-editor-persistence";
import { submitLoginAndRequireSuccess } from "../../../utils/login-langflow";
import { renameFlow } from "../../../utils/rename-flow";

const USER_PASSWORD = "authz-e2e-only-password"; // pragma: allowlist secret
const SUPERUSER_PASSWORD = "test-superuser-password"; // pragma: allowlist secret

type ApiUser = Awaited<ReturnType<typeof createActiveUserViaApi>>;

type ApiProject = {
  id: string;
  name: string;
  user_id: string;
  owner_username?: string | null;
  edit_revision: number;
};

type ApiFlow = {
  id: string;
  name: string;
  description: string;
  data: FlowData;
  folder_id: string | null;
  user_id: string;
  owner_username?: string | null;
  edit_revision: number;
};

type ApiShare = {
  id: string;
  resource_type: "flow" | "project";
  resource_id: string;
  scope: "user" | "team";
  target_id: string;
  permission_level: "execute" | "write";
  revision: number;
};

type Team = {
  id: string;
  team_name: string;
};

type AuthenticatedPage = {
  context: BrowserContext;
  page: Page;
  identity: { id: string; username: string };
};

async function requireStatus(
  response: APIResponse | PlaywrightResponse,
  expected: number | number[],
  action: string,
): Promise<void> {
  const statuses = Array.isArray(expected) ? expected : [expected];
  if (!statuses.includes(response.status())) {
    throw new Error(
      `${action} returned ${response.status()}: ${await response.text()}`,
    );
  }
}

async function responseJson<T>(
  response: APIResponse | PlaywrightResponse,
  expected: number | number[],
  action: string,
): Promise<T> {
  await requireStatus(response, expected, action);
  return (await response.json()) as T;
}

async function expectTeamPageReflow(page: Page, testId: string): Promise<void> {
  const surface = page.getByTestId(testId);
  const search = surface.getByRole("textbox", {
    name: "Search teams",
    exact: true,
  });
  await search.fill("Authz");
  await expect(
    surface.locator("label").filter({ hasText: "Search teams" }),
  ).toBeVisible();
  await search.clear();
  await expect(
    surface.getByRole("textbox", { name: "Team name", exact: true }),
  ).toBeVisible();

  const viewport = page.viewportSize();
  const fontSize = await page.evaluate(
    () => document.documentElement.style.fontSize,
  );
  try {
    for (const state of [
      { width: 320, fontSize: "" },
      { width: 1280, fontSize: "200%" },
    ]) {
      await page.setViewportSize({ width: state.width, height: 900 });
      await page.evaluate((size) => {
        document.documentElement.style.fontSize = size;
      }, state.fontSize);
      await expect
        .poll(() =>
          surface.evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            return (
              bounds.left >= -1 &&
              bounds.right <= window.innerWidth + 1 &&
              element.scrollWidth <= element.clientWidth + 1 &&
              Array.from(
                element.querySelectorAll("button, input, textarea"),
              ).every((control) => {
                const rect = control.getBoundingClientRect();
                return (
                  !control.getClientRects().length ||
                  (rect.left >= -1 && rect.right <= window.innerWidth + 1)
                );
              })
            );
          }),
        )
        .toBe(true);
    }
  } finally {
    await page.evaluate((size) => {
      document.documentElement.style.fontSize = size;
    }, fontSize);
    if (viewport) await page.setViewportSize(viewport);
  }

  const activeSwitch = surface.getByRole("switch", { name: "Team active" });
  if (await activeSwitch.count()) {
    try {
      for (const colorScheme of ["light", "dark"] as const) {
        await page.emulateMedia({ forcedColors: "active", colorScheme });
        await expect
          .poll(() =>
            activeSwitch.locator("span").evaluate((thumb) => {
              const style = getComputedStyle(thumb);
              return (
                Number.parseFloat(style.borderTopWidth) >= 1 &&
                style.borderTopStyle === "solid" &&
                style.borderTopColor !== style.backgroundColor
              );
            }),
          )
          .toBe(true);
      }
    } finally {
      await page.emulateMedia({ forcedColors: null, colorScheme: null });
    }
  }
}

async function login(
  browser: Browser,
  username: string,
  password = USER_PASSWORD,
): Promise<AuthenticatedPage> {
  const context = await browser.newContext();
  const page = await context.newPage();
  const identity = await authenticatePage(page, username, password);
  return { context, page, identity };
}

async function authenticatePage(
  page: Page,
  username: string,
  password = USER_PASSWORD,
): Promise<{ id: string; username: string }> {
  await page.goto("/");
  await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
    timeout: TIMEOUTS.long,
  });
  await page.getByPlaceholder(TEXTS.placeholderUsername).fill(username);
  await page.getByPlaceholder(TEXTS.placeholderPassword).fill(password);
  const identityResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/users/whoami"
    );
  });
  await submitLoginAndRequireSuccess(page);
  const identity = await responseJson<{ id: string; username: string }>(
    await identityResponse,
    200,
    `load authenticated identity for ${username}`,
  );
  expect(identity.username).toBe(username);
  await expect(page.getByTestId("user-profile-settings")).toBeVisible({
    timeout: TIMEOUTS.long,
  });
  return identity;
}

async function createProject(page: Page, name: string): Promise<ApiProject> {
  return responseJson<ApiProject>(
    await page.request.post("/api/v1/projects/", {
      data: { name, description: "Authorization E2E project" },
    }),
    201,
    `create project ${name}`,
  );
}

const emptyFlowData = (): FlowData => ({
  nodes: [],
  edges: [],
  viewport: { x: 0, y: 0, zoom: 1 },
});

async function createFlow(
  page: Page,
  projectId: string,
  name: string,
): Promise<ApiFlow> {
  return responseJson<ApiFlow>(
    await page.request.post("/api/v1/flows/", {
      data: {
        name,
        description: "Authorization E2E workflow",
        folder_id: projectId,
        data: emptyFlowData(),
      },
    }),
    201,
    `create flow ${name}`,
  );
}

async function getFlow(page: Page, flowId: string): Promise<ApiFlow> {
  return responseJson<ApiFlow>(
    await page.request.get(`/api/v1/flows/${flowId}`),
    200,
    `read flow ${flowId}`,
  );
}

async function createShare(
  page: Page,
  input: {
    resourceType: "flow" | "project";
    resourceId: string;
    scope: "user" | "team";
    targetId: string;
    permission: "execute" | "write";
  },
): Promise<ApiShare> {
  return responseJson<ApiShare>(
    await page.request.post("/api/v1/authz/shares", {
      data: {
        resource_type: input.resourceType,
        resource_id: input.resourceId,
        scope: input.scope,
        target_id: input.targetId,
        permission_level: input.permission,
      },
    }),
    201,
    `share ${input.resourceType} ${input.resourceId}`,
  );
}

async function updateShare(
  page: Page,
  share: ApiShare,
  permission: "execute" | "write",
): Promise<ApiShare> {
  return responseJson<ApiShare>(
    await page.request.patch(`/api/v1/authz/shares/${share.id}`, {
      headers: {
        "If-Match": `"share:${share.id}:${share.revision}"`,
      },
      data: { permission_level: permission },
    }),
    200,
    `update share ${share.id}`,
  );
}

async function addInitialTeamMember(
  page: Page,
  dialog: Locator,
  username: string,
  role: "Admin" | "Maintainer" | "User",
): Promise<void> {
  const picker = dialog.getByTestId("team-member-picker");
  await picker.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: role, exact: true }).click();
  const searchResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/authz/recipients" &&
      url.searchParams.get("q") === username
    );
  });
  await picker.getByLabel("Search users").fill(username);
  const result = await responseJson<{
    items: Array<{ id: string; display_name: string }>;
  }>(await searchResponse, 200, `search for initial team member ${username}`);
  expect(result.items.map((item) => item.display_name)).toContain(username);
  await expect(page).toHaveURL(/\/admin\?tab=teams$/);
  await picker.getByRole("button", { name: username, exact: true }).click();
  await picker.getByRole("button", { name: "Add member" }).click();
}

async function shareFromDialog(
  page: Page,
  input: {
    resourceType: "flow" | "project";
    resourceId: string;
    recipientType: "User" | "Team";
    recipientName: string;
    permission: "execute" | "write";
  },
): Promise<ApiShare> {
  const dialog = page.getByTestId("resource-share-dialog");
  await expect(dialog).toBeVisible({ timeout: TIMEOUTS.standard });
  await dialog
    .getByRole("radio", { name: input.recipientType, exact: true })
    .click();
  await dialog.getByLabel("Search recipients").fill(input.recipientName);
  await dialog
    .getByRole("button", { name: input.recipientName, exact: true })
    .click();
  const permissionLabel =
    input.permission === "execute"
      ? "Not editable — Can use"
      : "Editable — Can edit";
  await dialog
    .getByRole("radio", { name: new RegExp(`^${permissionLabel}`) })
    .click();

  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/authz/shares",
  );
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  const share = await responseJson<ApiShare>(
    await createResponse,
    201,
    `share ${input.resourceType} through dialog`,
  );
  await expect(
    dialog.getByText(input.recipientName, { exact: true }),
  ).toBeVisible({ timeout: TIMEOUTS.standard });
  return share;
}

test.describe("registered team and resource sharing", () => {
  test.describe.configure({ mode: "serial", retries: 0 });

  const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const teamName = `Authz Team ${runId}`;
  const usernames = {
    owner: `authz-owner-${runId}`,
    teamAdmin: `authz-team-admin-${runId}`,
    maintainer: `authz-maintainer-${runId}`,
    teamUser: `authz-team-user-${runId}`,
    direct: `authz-direct-${runId}`,
    outsider: `authz-outsider-${runId}`,
  };

  const contexts: BrowserContext[] = [];
  let adminPage: Page;
  let ownerPage: Page;
  let teamAdminPage: Page;
  let maintainerPage: Page;
  let teamUserPage: Page;
  let directPage: Page;
  let outsiderPage: Page;
  let owner: ApiUser;
  let teamAdmin: ApiUser;
  let maintainer: ApiUser;
  let teamUser: ApiUser;
  let direct: ApiUser;
  let outsider: ApiUser;
  let team: Team;
  let runnableFlow: ApiFlow;
  let runnableProjectId: string;
  let directShare: ApiShare;
  let teamProject: ApiProject;
  let teamProjectOwnerFlow: ApiFlow;
  let teamProjectMemberFlow: ApiFlow;

  test.beforeAll(async ({ browser }, testInfo) => {
    if (process.env.LANGFLOW_E2E_AUTHZ !== "true") {
      throw new Error(
        "Authorization journeys require LANGFLOW_E2E_AUTHZ=true and the registered Casbin server configuration.",
      );
    }

    await testInfo.attach("authorization-service", {
      body: assertAuthzStartup(readFileSync(AUTHZ_STARTUP_LOG, "utf8")),
      contentType: "text/plain",
    });

    const adminSession = await login(browser, "langflow", SUPERUSER_PASSWORD);
    contexts.push(adminSession.context);
    adminPage = adminSession.page;

    const capabilities = await responseJson<AuthorizationCapabilities>(
      await adminPage.request.get("/api/v1/authz/capabilities"),
      200,
      "read registered authorization capabilities",
    );
    expect(capabilities).toMatchObject({
      enforcement_active: true,
      service_ready: true,
      team_roles_supported: true,
      user_team_sharing_supported: true,
      conditional_writes_required: true,
    });

    const users: ApiUser[] = [];
    for (const username of Object.values(usernames)) {
      users.push(
        await createActiveUserViaApi(adminPage, {
          username,
          password: USER_PASSWORD,
        }),
      );
    }
    [owner, teamAdmin, maintainer, teamUser, direct, outsider] = users;

    const sessions: AuthenticatedPage[] = [];
    for (const username of Object.values(usernames)) {
      sessions.push(await login(browser, username));
    }
    expect(new Set(sessions.map((session) => session.identity.id)).size).toBe(
      sessions.length,
    );
    expect(sessions.map((session) => session.identity.id).sort()).toEqual(
      [owner, teamAdmin, maintainer, teamUser, direct, outsider]
        .map((user) => user.id)
        .sort(),
    );
    contexts.push(...sessions.map((session) => session.context));
    [
      ownerPage,
      teamAdminPage,
      maintainerPage,
      teamUserPage,
      directPage,
      outsiderPage,
    ] = sessions.map((session) => session.page);
  });

  test.afterAll(async () => {
    await Promise.all(contexts.map((context) => context.close()));
  });

  test(
    "[AUTHZ-JOURNEY-01] Platform Admin creates a non-empty team and scoped roles control each member UI",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async ({ page: a11yPage }) => {
      await adminPage.goto("/admin");
      await expect(adminPage.getByTestId("admin-add-user")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(
        adminPage.getByRole("tab", { name: "Users", exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      await adminPage.getByRole("tab", { name: "Teams", exact: true }).click();
      await expect(adminPage).toHaveURL(/\/admin\?tab=teams$/);
      await expect(adminPage.getByTestId("admin-teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await adminPage.getByRole("button", { name: "Create team" }).click();
      const dialog = adminPage.getByRole("dialog", { name: "Create team" });
      await dialog.getByLabel("Team name").fill(teamName);
      await dialog.getByLabel("Administrative domain").fill(`authz-${runId}`);
      await addInitialTeamMember(
        adminPage,
        dialog,
        teamAdmin.username,
        "Admin",
      );
      await addInitialTeamMember(
        adminPage,
        dialog,
        maintainer.username,
        "Maintainer",
      );
      await addInitialTeamMember(adminPage, dialog, teamUser.username, "User");

      const createResponse = adminPage.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === "/api/v1/authz/teams",
      );
      await dialog.getByRole("button", { name: "Create team" }).click();
      team = await responseJson<Team>(
        await createResponse,
        201,
        "create team through administration UI",
      );
      await expect(
        adminPage.getByRole("heading", { name: teamName }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await teamAdminPage.goto("/teams");
      await expect(teamAdminPage.getByTestId("teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(teamAdminPage.getByLabel("Team name")).toBeEnabled();
      await expect(
        teamAdminPage.getByLabel("Administrative domain"),
      ).toBeDisabled();

      await maintainerPage.goto("/teams");
      await expect(maintainerPage.getByTestId("teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(maintainerPage.getByLabel("Team name")).toBeDisabled();
      await expect(
        maintainerPage.getByTestId("team-member-picker"),
      ).toBeVisible();

      await teamUserPage.goto("/teams");
      await expect(teamUserPage.getByTestId("teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(teamUserPage.getByLabel("Team name")).toBeDisabled();
      await expect(teamUserPage.getByTestId("team-member-picker")).toHaveCount(
        0,
      );

      await authenticatePage(a11yPage, "langflow", SUPERUSER_PASSWORD);
      await a11yPage.goto("/admin");
      await expect(a11yPage.getByTestId("admin-add-user")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(a11yPage.getByRole("main")).toHaveCount(1);
      await expect(
        a11yPage.getByRole("table", { name: "Users" }),
      ).toBeVisible();
      await a11yPage.runA11yScan("authz-admin-users");
      await a11yPage
        .getByRole("textbox", { name: "Search users" })
        .fill(owner.username);
      await a11yPage
        .getByRole("button", { name: "Search", exact: true })
        .click();
      await expect(
        a11yPage.getByRole("button", {
          name: `Edit ${owner.username}`,
          exact: true,
        }),
      ).toBeVisible();
      for (const action of [
        "Add User",
        `Edit ${owner.username}`,
        `Delete ${owner.username}`,
      ]) {
        const trigger = a11yPage.getByRole("button", {
          name: action,
          exact: true,
        });
        await trigger.focus();
        await a11yPage.keyboard.press("Enter");
        const userDialog = a11yPage.getByRole("dialog");
        await expect(userDialog).toBeVisible();
        await a11yPage.runA11yScan(
          `authz-admin-users-${action.split(" ")[0].toLowerCase()}-dialog`,
        );
        await a11yPage.keyboard.press("Tab");
        await expect
          .poll(() =>
            userDialog.evaluate((node) =>
              node.contains(document.activeElement),
            ),
          )
          .toBe(true);
        await a11yPage.keyboard.press("Shift+Tab");
        await expect
          .poll(() =>
            userDialog.evaluate((node) =>
              node.contains(document.activeElement),
            ),
          )
          .toBe(true);
        // Leave the Close tooltip before testing the dialog's Escape handler.
        await a11yPage.keyboard.press("Tab");
        await expect(a11yPage.getByRole("tooltip")).toBeHidden();
        await a11yPage.keyboard.press("Escape");
        await expect(userDialog).toBeHidden();
        await expect(trigger).toBeFocused();
      }
      await a11yPage
        .getByRole("textbox", { name: "Search users" })
        .fill(`absent-${runId}`);
      await a11yPage
        .getByRole("button", { name: "Search", exact: true })
        .click();
      await expect(
        a11yPage.getByText("No users found.", { exact: true }),
      ).toBeVisible();
      await a11yPage.runA11yScan("authz-admin-users-empty");
      await a11yPage.goto("/admin/teams");
      await expect(a11yPage).toHaveURL(/\/admin\?tab=teams$/);
      await expect(a11yPage.getByTestId("admin-teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await a11yPage.runA11yScan("authz-admin-teams");
      await expectTeamPageReflow(a11yPage, "admin-teams-page");
    },
  );

  test(
    "[AUTHZ-JOURNEY-02] ordinary owner shares a workflow as Can use and recipient runs but cannot save",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async ({ page: a11yPage }) => {
      const bootstrapProject = await createProject(
        ownerPage,
        `Owner bootstrap project ${runId}`,
      );
      const bootstrapFlow = await createFlow(
        ownerPage,
        bootstrapProject.id,
        `Runnable shared flow ${runId}`,
      );
      await ownerPage.goto(
        `/flow/${bootstrapFlow.id}/folder/${bootstrapProject.id}`,
      );
      await populateTextInputOutputFlow(ownerPage);
      const flowId = new URL(ownerPage.url()).pathname.match(
        /\/flow\/([^/?#]+)/,
      )?.[1];
      if (!flowId) throw new Error("Runnable flow id was not present in URL");
      await renameFlow(ownerPage, {
        flowName: `Runnable shared flow ${runId}`,
        flowDescription: "Owner version",
      });
      await flushPendingFlowAutosave(ownerPage);
      expect(await runTextInputOutputFlow(ownerPage, "owner seed")).toContain(
        "owner seed",
      );
      await flushPendingFlowAutosave(ownerPage);
      runnableFlow = await getFlow(ownerPage, flowId);
      runnableProjectId = runnableFlow.folder_id ?? "";
      expect(runnableProjectId).not.toBe("");

      await ownerPage.getByTestId("publish-button").click();
      await ownerPage.getByTestId(`share-flow-${flowId}`).click();
      directShare = await shareFromDialog(ownerPage, {
        resourceType: "flow",
        resourceId: flowId,
        recipientType: "User",
        recipientName: direct.username,
        permission: "execute",
      });

      await directPage.goto("/shared-with-me");
      await expect(
        directPage.getByText(runnableFlow.name, { exact: true }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await directPage.goto(`/flow/${flowId}`);
      await expect(
        directPage.getByRole("application", { name: "Text Output node" }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(
        directPage
          .getByRole("application", { name: "Text Input node" })
          .getByTestId("textarea_str_input_value"),
      ).toBeDisabled();
      await expect(
        directPage
          .getByRole("application", { name: "Text Output node" })
          .getByRole("button", { name: "Run component" }),
      ).toBeEnabled();
      const recipientRun = await responseJson<unknown>(
        await directPage.request.post("/api/v2/workflows", {
          data: {
            flow_id: flowId,
            input_value: "",
            mode: "sync",
            stream_protocol: "langflow",
            session_id: `authz-recipient-${runId}`,
          },
        }),
        200,
        "Can use recipient workflow execution",
      );
      expect(JSON.stringify(recipientRun)).toContain("owner seed");

      const latest = await getFlow(directPage, flowId);
      const denied = await directPage.request.patch(`/api/v1/flows/${flowId}`, {
        headers: {
          "If-Match": `"flow:${flowId}:${latest.edit_revision}"`,
        },
        data: { description: "must not persist" },
      });
      await requireStatus(denied, 403, "Can use recipient save denial");
      await directPage.getByTestId("publish-button").click();
      await expect(directPage.getByTestId(`share-flow-${flowId}`)).toHaveCount(
        0,
      );

      await authenticatePage(a11yPage, direct.username);
      await a11yPage.goto("/shared-with-me");
      await expect(
        a11yPage.getByText(runnableFlow.name, { exact: true }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await a11yPage.runA11yScan("authz-shared-with-me");
      await a11yPage.goto(`/flow/${flowId}`);
      await expect(
        a11yPage.getByRole("application", { name: "Text Output node" }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
    },
  );

  test(
    "[AUTHZ-JOURNEY-03] owner upgrades the same grant and recipient edits graph content visible to owner",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async ({ page: a11yPage }) => {
      await ownerPage.goto(`/flow/${runnableFlow.id}`);
      await ownerPage.getByTestId("publish-button").click();
      await ownerPage.getByTestId(`share-flow-${runnableFlow.id}`).click();
      const dialog = ownerPage.getByTestId("resource-share-dialog");
      const grant = dialog.getByTestId(`share-grant-${directShare.id}`);
      const updateResponse = ownerPage.waitForResponse(
        (response) =>
          response.request().method() === "PATCH" &&
          new URL(response.url()).pathname ===
            `/api/v1/authz/shares/${directShare.id}`,
      );
      await grant.getByRole("radio", { name: /^Editable — Can edit/ }).click();
      directShare = await responseJson<ApiShare>(
        await updateResponse,
        200,
        "upgrade workflow grant through dialog",
      );

      await directPage.goto(`/flow/${runnableFlow.id}`);
      const recipientInput = directPage
        .getByRole("application", { name: "Text Input node" })
        .getByTestId("textarea_str_input_value");
      await expect(recipientInput).toBeEnabled({ timeout: TIMEOUTS.standard });
      const marker = `edited-by-${direct.username}`;
      const autosaveResponse = directPage.waitForResponse(
        (response) =>
          response.request().method() === "PATCH" &&
          new URL(response.url()).pathname ===
            `/api/v1/flows/${runnableFlow.id}` &&
          response.request().postData()?.includes(marker) === true,
      );
      await recipientInput.fill(marker);
      await flushPendingFlowAutosave(directPage);
      const saved = await responseJson<ApiFlow>(
        await autosaveResponse,
        200,
        "Can edit recipient UI autosave",
      );
      expect(JSON.stringify(saved.data)).toContain(marker);

      const ownerView = await getFlow(ownerPage, runnableFlow.id);
      expect(JSON.stringify(ownerView.data)).toContain(marker);
      await ownerPage.goto(`/flow/${runnableFlow.id}`);
      await expect(
        ownerPage
          .getByRole("application", { name: "Text Input node" })
          .getByTestId("textarea_str_input_value"),
      ).toHaveValue(marker, { timeout: TIMEOUTS.standard });

      // Check the new dialog's controls without including the existing graph
      // editor's unrelated ARIA issues in this feature's acceptance scope.
      const dialogFlow = await createFlow(
        ownerPage,
        runnableProjectId,
        `Share dialog controls ${runId}`,
      );
      const dialogShare = await createShare(ownerPage, {
        resourceType: "flow",
        resourceId: dialogFlow.id,
        scope: "user",
        targetId: direct.id,
        permission: "write",
      });
      await authenticatePage(a11yPage, owner.username);
      await a11yPage.goto(`/flow/${dialogFlow.id}`);
      await a11yPage.getByTestId("publish-button").click();
      await a11yPage.getByTestId(`share-flow-${dialogFlow.id}`).click();
      await expect(a11yPage.getByTestId("resource-share-dialog")).toBeVisible();
      await expect(
        a11yPage.getByTestId(`share-grant-${dialogShare.id}`),
      ).toBeVisible();
      await a11yPage.runA11yScan("authz-resource-share-dialog");
      await a11yPage.getByLabel("Search recipients").focus();
      const shareDialog = a11yPage.getByTestId("resource-share-dialog");
      const recipientType = shareDialog.getByRole("radiogroup", {
        name: "Recipient type",
      });
      await a11yPage.keyboard.press("Shift+Tab");
      await expect(
        recipientType.getByRole("radio", { name: "User", exact: true }),
      ).toBeFocused();
      await a11yPage.keyboard.press("Shift+Tab");
      await expect(
        shareDialog.getByRole("button", { name: "Close", exact: true }).last(),
      ).toBeFocused();
      await a11yPage.keyboard.press("Tab");
      await a11yPage.keyboard.press("ArrowRight", { delay: 100 });
      await expect(
        recipientType.getByRole("radio", { name: "Team", exact: true }),
      ).toBeChecked();
      await a11yPage.keyboard.press("ArrowLeft", { delay: 100 });
      await expect(
        recipientType.getByRole("radio", { name: "User", exact: true }),
      ).toBeChecked();
      await a11yPage.getByLabel("Search recipients").focus();
      await a11yPage.keyboard.press("Escape");
      await expect(a11yPage.getByTestId("resource-share-dialog")).toBeHidden();
      await expect(a11yPage.getByTestId("publish-button")).toBeFocused();
    },
  );

  test(
    "[AUTHZ-JOURNEY-04] team project share covers existing, future, and collaborator-created workflows",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async ({ page: a11yPage }) => {
      teamProject = await createProject(
        ownerPage,
        `Team inherited project ${runId}`,
      );
      teamProjectOwnerFlow = await createFlow(
        ownerPage,
        teamProject.id,
        `Existing inherited flow ${runId}`,
      );

      await ownerPage.goto(`/all/folder/${teamProject.id}`);
      await ownerPage
        .getByTestId(`more-options-button_${teamProject.id}`)
        .click();
      await ownerPage.getByTestId(`share-project-${teamProject.id}`).click();
      await shareFromDialog(ownerPage, {
        resourceType: "project",
        resourceId: teamProject.id,
        recipientType: "Team",
        recipientName: teamName,
        permission: "write",
      });

      const futureOwnerFlow = await createFlow(
        ownerPage,
        teamProject.id,
        `Future inherited flow ${runId}`,
      );
      const memberProject = await responseJson<{
        folder: ApiProject;
        flows: { items: ApiFlow[] } | ApiFlow[];
      }>(
        await teamUserPage.request.get(`/api/v1/projects/${teamProject.id}`),
        200,
        "team member reads shared project",
      );
      const memberFlows = Array.isArray(memberProject.flows)
        ? memberProject.flows
        : memberProject.flows.items;
      expect(memberFlows.map((flow) => flow.id)).toEqual(
        expect.arrayContaining([teamProjectOwnerFlow.id, futureOwnerFlow.id]),
      );
      for (const memberPage of [teamAdminPage, maintainerPage]) {
        expect((await getFlow(memberPage, teamProjectOwnerFlow.id)).id).toBe(
          teamProjectOwnerFlow.id,
        );
        expect((await getFlow(memberPage, futureOwnerFlow.id)).id).toBe(
          futureOwnerFlow.id,
        );
      }

      teamProjectMemberFlow = await createFlow(
        teamUserPage,
        teamProject.id,
        `Collaborator-owned flow ${runId}`,
      );
      expect(teamProjectMemberFlow.user_id).toBe(teamUser.id);
      const visibleToProjectOwner = await getFlow(
        ownerPage,
        teamProjectMemberFlow.id,
      );
      expect(visibleToProjectOwner.user_id).toBe(teamUser.id);

      await authenticatePage(a11yPage, teamAdmin.username);
      await a11yPage.goto("/teams");
      await expect(a11yPage.getByTestId("teams-page")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await a11yPage.runA11yScan("authz-member-teams");
      await expectTeamPageReflow(a11yPage, "teams-page");
    },
  );

  test(
    "[AUTHZ-JOURNEY-05] removing a member revokes new team requests but preserves ownership and other grants",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async () => {
      await requireStatus(
        await adminPage.request.delete(
          `/api/v1/authz/teams/${team.id}/members/${teamUser.id}`,
        ),
        204,
        "remove team member",
      );

      await requireStatus(
        await teamUserPage.request.get(
          `/api/v1/flows/${teamProjectOwnerFlow.id}`,
        ),
        404,
        "removed member shared flow read denial",
      );
      await requireStatus(
        await teamUserPage.request.get(`/api/v1/projects/${teamProject.id}`),
        404,
        "removed member shared project read denial",
      );
      const retainedOwnedFlow = await getFlow(
        teamUserPage,
        teamProjectMemberFlow.id,
      );
      expect(retainedOwnedFlow.user_id).toBe(teamUser.id);

      // This member has inherited access before the direct grant is added.
      // Suspending the team must remove only the inherited source.
      await getFlow(teamAdminPage, teamProjectMemberFlow.id);
      await createShare(teamUserPage, {
        resourceType: "flow",
        resourceId: teamProjectMemberFlow.id,
        scope: "user",
        targetId: teamAdmin.id,
        permission: "execute",
      });

      await requireStatus(
        await adminPage.request.patch(`/api/v1/authz/teams/${team.id}`, {
          data: { is_active: false },
        }),
        200,
        "suspend team",
      );
      await requireStatus(
        await teamAdminPage.request.get(
          `/api/v1/flows/${teamProjectOwnerFlow.id}`,
        ),
        404,
        "suspended team no longer grants workflow access",
      );
      expect((await getFlow(teamAdminPage, teamProjectMemberFlow.id)).id).toBe(
        teamProjectMemberFlow.id,
      );
      const suspendedTeam = await responseJson<AuthorizationTeam>(
        await teamAdminPage.request.get(`/api/v1/authz/teams/${team.id}`),
        200,
        "suspended team retains its admin's management access",
      );
      expect(suspendedTeam).toMatchObject({
        is_active: false,
        current_user_role: "admin",
        capabilities: { can_update: true, can_set_active: false },
      });
      const survivingDirectGrant = await getFlow(directPage, runnableFlow.id);
      expect(survivingDirectGrant.id).toBe(runnableFlow.id);
    },
  );

  test(
    "[AUTHZ-JOURNEY-06] downgrade rejects an open editor save and retains local unsaved content",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async () => {
      await directPage.goto(`/flow/${runnableFlow.id}`);
      const input = directPage
        .getByRole("application", { name: "Text Input node" })
        .getByTestId("textarea_str_input_value");
      await expect(input).toBeEnabled({ timeout: TIMEOUTS.standard });

      let releasePatch!: () => void;
      let captureRoute!: (route: Route) => void;
      const patchGate = new Promise<void>((resolve) => {
        releasePatch = resolve;
      });
      const capturedRoute = new Promise<Route>((resolve) => {
        captureRoute = resolve;
      });
      const marker = `unsaved-${runId}`;
      let firstPatch = true;
      const routePattern = `**/api/v1/flows/${runnableFlow.id}`;
      await directPage.route(routePattern, async (route) => {
        if (
          route.request().method() !== "PATCH" ||
          !route.request().postData()?.includes(marker) ||
          !firstPatch
        ) {
          await route.continue();
          return;
        }
        firstPatch = false;
        captureRoute(route);
        await patchGate;
        await route.continue();
      });

      const saves: PlaywrightResponse[] = [];
      const recordSave = (response: PlaywrightResponse) => {
        if (
          response.request().method() === "PATCH" &&
          new URL(response.url()).pathname ===
            `/api/v1/flows/${runnableFlow.id}` &&
          response.request().postData()?.includes(marker)
        )
          saves.push(response);
      };
      directPage.on("response", recordSave);
      await input.fill(marker);
      await capturedRoute;
      directShare = await updateShare(ownerPage, directShare, "execute");
      const deniedResponse = directPage.waitForResponse(
        (response) =>
          response.request().method() === "PATCH" &&
          new URL(response.url()).pathname ===
            `/api/v1/flows/${runnableFlow.id}` &&
          response.request().postData()?.includes(marker) === true,
      );
      releasePatch();
      await requireStatus(
        await deniedResponse,
        403,
        "save admitted after access downgrade",
      );
      await expect(input).toHaveValue(marker);
      await flushPendingFlowAutosave(directPage);
      await expect(input).toBeDisabled({ timeout: TIMEOUTS.standard });
      expect(saves.map((response) => response.status())).toEqual([403]);
      expect(
        JSON.stringify((await getFlow(ownerPage, runnableFlow.id)).data),
      ).not.toContain(marker);
      await expect(
        directPage.getByTestId("user-profile-settings"),
      ).toBeVisible();
      directPage.off("response", recordSave);
      await directPage.unroute(routePattern);
    },
  );

  test(
    "[AUTHZ-JOURNEY-07] simultaneous editors receive one success and one stale-write conflict without replay",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async () => {
      directShare = await updateShare(ownerPage, directShare, "write");
      const current = await getFlow(ownerPage, runnableFlow.id);
      const etag = `"flow:${runnableFlow.id}:${current.edit_revision}"`;
      const [ownerSave, collaboratorSave] = await Promise.all([
        ownerPage.request.patch(`/api/v1/flows/${runnableFlow.id}`, {
          headers: { "If-Match": etag },
          data: { description: `owner-concurrent-${runId}` },
        }),
        directPage.request.patch(`/api/v1/flows/${runnableFlow.id}`, {
          headers: { "If-Match": etag },
          data: { description: `collaborator-concurrent-${runId}` },
        }),
      ]);
      const statuses = [ownerSave.status(), collaboratorSave.status()].sort();
      expect(statuses).toEqual([200, 412]);

      const conflict =
        ownerSave.status() === 412 ? ownerSave : collaboratorSave;
      const conflictBody = (await conflict.json()) as {
        detail?: { code?: string };
      };
      expect(conflictBody.detail?.code).toBe("RESOURCE_CHANGED");
      const finalFlow = await getFlow(ownerPage, runnableFlow.id);
      expect([
        `owner-concurrent-${runId}`,
        `collaborator-concurrent-${runId}`,
      ]).toContain(finalFlow.description);
      expect(finalFlow.edit_revision).toBe(current.edit_revision + 1);

      // Keep the actual editor open across a competing write. The API race
      // above alone cannot prove draft preservation or stopped autosaves.
      await directPage.goto(`/flow/${runnableFlow.id}`);
      const input = directPage
        .getByRole("application", { name: "Text Input node" })
        .getByTestId("textarea_str_input_value");
      await expect(input).toBeEnabled({ timeout: TIMEOUTS.standard });
      await flushPendingFlowAutosave(directPage);
      const editorVersion = await getFlow(ownerPage, runnableFlow.id);
      const marker = `stale-editor-${runId}`;
      let releaseSave!: () => void;
      let captureSave!: () => void;
      const saveGate = new Promise<void>((resolve) => {
        releaseSave = resolve;
      });
      const capturedSave = new Promise<void>((resolve) => {
        captureSave = resolve;
      });
      let saveCount = 0;
      const routePattern = `**/api/v1/flows/${runnableFlow.id}`;
      await directPage.route(routePattern, async (route) => {
        if (
          route.request().method() === "PATCH" &&
          route.request().postData()?.includes(marker)
        ) {
          saveCount++;
          captureSave();
          await saveGate;
        }
        await route.continue();
      });
      await input.fill(marker);
      await capturedSave;
      const winner = await responseJson<ApiFlow>(
        await ownerPage.request.patch(`/api/v1/flows/${runnableFlow.id}`, {
          headers: {
            "If-Match": `"flow:${runnableFlow.id}:${editorVersion.edit_revision}"`,
          },
          data: { description: `newer-owner-version-${runId}` },
        }),
        200,
        "owner saves while collaborator draft is pending",
      );
      const staleResponse = directPage.waitForResponse(
        (response) =>
          response.request().method() === "PATCH" &&
          new URL(response.url()).pathname ===
            `/api/v1/flows/${runnableFlow.id}` &&
          response.request().postData()?.includes(marker) === true,
      );
      releaseSave();
      await requireStatus(await staleResponse, 412, "open editor stale save");
      await flushPendingFlowAutosave(directPage);
      await expect(input).toHaveValue(marker);
      await input.fill(`${marker}-continued`);
      await flushPendingFlowAutosave(directPage);
      await expect(input).toHaveValue(`${marker}-continued`);
      expect(saveCount).toBe(1);
      const persisted = await getFlow(ownerPage, runnableFlow.id);
      expect(persisted.description).toBe(winner.description);
      expect(persisted.edit_revision).toBe(winner.edit_revision);
      expect(JSON.stringify(persisted.data)).not.toContain(marker);
      await directPage.unroute(routePattern);
    },
  );

  test(
    "[AUTHZ-JOURNEY-08] direct flow share exposes neither its private parent nor sibling workflows",
    { tag: ["@authz", "@api", "@database", "@workspace", "@release"] },
    async () => {
      const privateProject = await createProject(
        ownerPage,
        `Private direct-only project ${runId}`,
      );
      const sharedFlow = await createFlow(
        ownerPage,
        privateProject.id,
        `Direct-only flow ${runId}`,
      );
      const sibling = await createFlow(
        ownerPage,
        privateProject.id,
        `Private sibling ${runId}`,
      );
      await createShare(ownerPage, {
        resourceType: "flow",
        resourceId: sharedFlow.id,
        scope: "user",
        targetId: outsider.id,
        permission: "execute",
      });

      await outsiderPage.goto("/shared-with-me");
      await expect(
        outsiderPage.getByText(sharedFlow.name, { exact: true }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(
        outsiderPage.getByText(`Owned by ${owner.username}`, { exact: true }),
      ).toBeVisible();
      expect((await getFlow(outsiderPage, sharedFlow.id)).id).toBe(
        sharedFlow.id,
      );
      await requireStatus(
        await outsiderPage.request.get(`/api/v1/flows/${sibling.id}`),
        404,
        "direct recipient sibling privacy",
      );
      await requireStatus(
        await outsiderPage.request.get(`/api/v1/projects/${privateProject.id}`),
        404,
        "direct recipient parent privacy",
      );

      const visibleFlows = await responseJson<ApiFlow[]>(
        await outsiderPage.request.get("/api/v1/flows/?get_all=true"),
        200,
        "direct recipient flow list",
      );
      expect(visibleFlows.map((flow) => flow.id)).toContain(sharedFlow.id);
      expect(visibleFlows.map((flow) => flow.id)).not.toContain(sibling.id);
      const visibleProjects = await responseJson<ApiProject[]>(
        await outsiderPage.request.get("/api/v1/projects/"),
        200,
        "direct recipient project list",
      );
      expect(visibleProjects.map((project) => project.id)).not.toContain(
        privateProject.id,
      );

      // The same browser must discard the owner's resource and permission
      // snapshots when it switches to the direct recipient without a reload.
      const switchedPage = ownerPage;
      await switchedPage.goto(`/all/folder/${privateProject.id}`);
      await expect(
        switchedPage.getByText(sibling.name, { exact: true }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await switchedPage.getByTestId("user-profile-settings").click();
      const [logoutResponse] = await Promise.all([
        switchedPage.waitForResponse(
          (response) =>
            response.request().method() === "POST" &&
            new URL(response.url()).pathname === "/api/v1/logout",
        ),
        switchedPage
          .getByRole("menuitem", { name: TEXTS.logout, exact: true })
          .click(),
      ]);
      await requireStatus(logoutResponse, 200, "owner logout");
      await expect(
        switchedPage.getByRole("button", { name: TEXTS.signIn }),
      ).toBeVisible();
      await switchedPage
        .getByPlaceholder(TEXTS.placeholderUsername)
        .fill(outsider.username);
      await switchedPage
        .getByPlaceholder(TEXTS.placeholderPassword)
        .fill(USER_PASSWORD);
      await submitLoginAndRequireSuccess(switchedPage);
      await expect(
        switchedPage.getByTestId("user-profile-settings"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(
        switchedPage.getByText(privateProject.name, { exact: true }),
      ).toHaveCount(0);
      await expect(
        switchedPage.getByText(sibling.name, { exact: true }),
      ).toHaveCount(0);
      await switchedPage.getByTestId("user-profile-settings").click();
      await switchedPage.getByTestId("menu-shared-with-me-button").click();
      const sharedRow = switchedPage.getByRole("listitem").filter({
        has: switchedPage.getByText(sharedFlow.name, { exact: true }),
      });
      await sharedRow
        .getByRole("button", { name: "Open", exact: true })
        .click();
      await switchedPage.getByTestId("publish-button").click();
      await expect(
        switchedPage.getByTestId(`share-flow-${sharedFlow.id}`),
      ).toHaveCount(0);
    },
  );
});
