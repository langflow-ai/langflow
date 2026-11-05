import { expect, test } from "../fixtures";

for (const path of ["/flows", "/settings/migration"]) {
  test(
    `announces maintenance transitions on ${path}`,
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      await page.clock.install();
      let response:
        | { paused: boolean; maintenance: boolean; migration: boolean }
        | "external" = {
        paused: false,
        maintenance: false,
        migration: false,
      };
      let polls = 0;
      await page.route("**/api/v1/maintenance/status", async (route) => {
        polls += 1;
        await route.fulfill(
          response === "external"
            ? {
                status: 503,
                contentType: "application/json",
                body: JSON.stringify({
                  detail: {
                    code: "external_auth_maintenance",
                    message: "External authentication paused",
                  },
                }),
              }
            : {
                status: 200,
                contentType: "application/json",
                body: JSON.stringify(response),
              },
        );
      });
      await page.goto(path);
      const notice = page.getByTestId("changes-paused-notice");
      await expect(notice).toHaveAttribute("role", "status");
      await expect(notice).toBeEmpty();
      await expect.poll(() => polls).toBeGreaterThan(0);
      await notice.evaluate((element) => {
        element.setAttribute("data-live-region-proof", "original");
      });

      const poll = async () => {
        const previous = polls;
        await page.clock.fastForward(30_100);
        await expect.poll(() => polls).toBeGreaterThan(previous);
      };
      response = { paused: true, maintenance: true, migration: false };
      await poll();
      await expect(notice).toContainText(
        "Administrators can still make changes",
      );
      await expect(notice).toHaveAttribute(
        "data-live-region-proof",
        "original",
      );
      await page.runA11yScan(`maintenance-notice-${path}-database`);

      response = { paused: true, maintenance: true, migration: true };
      await poll();
      await expect(notice).toContainText("while it moves to a new one");
      await expect(notice).not.toContainText(
        "Administrators can still make changes",
      );
      await page.runA11yScan(`maintenance-notice-${path}-both`);

      page.expectServerError({
        method: "GET",
        path: "/api/v1/maintenance/status",
        status: 503,
        count: 1,
      });
      response = "external";
      await poll();
      await expect(notice).toContainText("External SSO sign-in is paused");
      await page.runA11yScan(`maintenance-notice-${path}-external`);

      response = { paused: false, maintenance: false, migration: false };
      await poll();
      await expect(notice).toBeEmpty();
      await expect(notice).toHaveAttribute(
        "data-live-region-proof",
        "original",
      );
    },
  );
}
