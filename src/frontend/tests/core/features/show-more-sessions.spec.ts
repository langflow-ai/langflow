import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";

// The sessions endpoint pages newest-first; the playground asks for one row
// more than a page (100) to learn whether an older page exists.
const sessions = Array.from({ length: 150 }, (_, i) => `older-session-${i}`);

test(
  "should load older sessions with Show more",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    await page.route("**/api/v1/monitor/messages/sessions*", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const params = new URL(route.request().url()).searchParams;
      const offset = Number(params.get("offset"));
      const limit = Number(params.get("limit"));
      await route.fulfill({ json: sessions.slice(offset, offset + limit) });
    });

    await openStarterProject(page, TEXTS.templateBasicPrompting);
    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    const rows = page.getByTestId(TID.sessionSelector);
    const showMore = page.getByRole("button", { name: "Show more sessions" });
    // Default session + the first page.
    await expect(rows).toHaveCount(101);

    await showMore.click();

    await expect(rows).toHaveCount(151);
    await expect(rows.last()).toHaveText("older-session-149");
    await expect(showMore).toHaveCount(0);
  },
);
