import echoFlow from "../../assets/a2a/echo-agent.json";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const SESSION_ID = "saved & +% conversation";
const SAVED_TEXT = "Message restored through a flow link";

// Runs only Chat Input -> Chat Output: no model, provider key or network call.
async function createConversation(
  page: Parameters<typeof awaitBootstrapTest>[0],
) {
  await awaitBootstrapTest(page, { skipModal: true });
  const created = await page.request.post("/api/v1/flows/", {
    data: { ...echoFlow, name: `Deep link ${crypto.randomUUID()}` },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };
  const run = await page.request.post(`/api/v1/run/session/${id}`, {
    data: {
      input_value: SAVED_TEXT,
      input_type: "chat",
      output_type: "chat",
      session_id: SESSION_ID,
    },
  });
  expect(run.ok(), await run.text()).toBeTruthy();
  return id;
}

function deepLink(flowId: string, sessionId = SESSION_ID) {
  return `/flow/${flowId}?playground=true&session=${encodeURIComponent(sessionId)}`;
}

test(
  "opens a saved conversation from an encoded flow link",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await createConversation(page);
    await page.goto(deepLink(flowId));

    await expect(page.getByTestId("playground-close-button")).toBeVisible();
    await expect(
      page.getByTestId("session-selector").filter({ hasText: SESSION_ID }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByTestId(`chat-message-AI-${SAVED_TEXT}`),
    ).toBeVisible();
  },
);

test(
  "keeps an older linked conversation when the first session page arrives later",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await createConversation(page);
    let releasePage!: () => void;
    const pageReady = new Promise<void>((resolve) => {
      releasePage = resolve;
    });
    await page.route(
      "**/api/v1/monitor/messages/sessions?**",
      async (route) => {
        await pageReady;
        await route.fulfill({
          json: Array.from({ length: 101 }, (_, index) => `recent-${index}`),
        });
      },
    );
    await page.goto(deepLink(flowId));
    const selected = page
      .getByTestId("session-selector")
      .filter({ hasText: SESSION_ID });
    await expect(selected).toHaveAttribute("aria-current", "page");
    releasePage();

    await expect(
      page.getByTestId("session-selector").filter({ hasText: "recent-0" }),
    ).toBeVisible();
    await expect(selected).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByTestId(`chat-message-AI-${SAVED_TEXT}`),
    ).toBeVisible();
  },
);

test(
  "falls back to the default session for an unknown linked conversation",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await createConversation(page);
    const lookup = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.pathname === "/api/v1/monitor/messages" &&
        url.searchParams.get("limit") === "1"
      );
    });
    await page.goto(deepLink(flowId, "missing-session"));
    expect(await (await lookup).json()).toEqual([]);

    await expect(
      page
        .getByTestId("session-selector")
        .filter({ hasText: "Default Session" }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page
        .getByTestId("session-selector")
        .filter({ hasText: "missing-session" }),
    ).toHaveCount(0);
    await expect(page.getByTestId(`chat-message-AI-${SAVED_TEXT}`)).toHaveCount(
      0,
    );
  },
);

test(
  "does not restore a pending link after closing and reopening the Playground",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await createConversation(page);
    let releaseLookup!: () => void;
    const lookupReady = new Promise<void>((resolve) => {
      releaseLookup = resolve;
    });
    await page.route("**/api/v1/monitor/messages?**", async (route) => {
      if (new URL(route.request().url()).searchParams.get("limit") !== "1")
        return route.continue();
      const response = await route.fetch();
      await lookupReady;
      await route.fulfill({ response });
    });
    await page.goto(deepLink(flowId));
    await page.getByTestId("playground-close-button").click();
    await expect(page.getByTestId("input-chat-playground")).toBeHidden();
    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await expect(page.getByTestId("input-chat-playground")).toBeVisible();
    const lookup = page.waitForResponse(
      (response) => new URL(response.url()).searchParams.get("limit") === "1",
    );
    releaseLookup();
    await (await lookup).finished();
    await page.evaluate(
      () =>
        new Promise<void>((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
        }),
    );

    await expect(
      page.getByTestId("session-selector").filter({ hasText: SESSION_ID }),
    ).not.toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId(`chat-message-AI-${SAVED_TEXT}`)).toHaveCount(
      0,
    );
  },
);
