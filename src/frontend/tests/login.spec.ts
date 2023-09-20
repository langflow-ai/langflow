import { test } from "@playwright/test";

test.describe("Login Tests", () => {
  test("Login_Success", async ({ page }) => {
    await page.route("**/api/v1/login", async (route) => {
      const json = {
        access_token:
          "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWNlM2FkOS1iZTE2LTRiNjgtOGRhYi1hYjA4YTVjMmZjZTkiLCJleHAiOjE2OTUyNTIwNTh9.MBYFwMhTcZnsW_L7p4qavUhSDylCllJQWUCJdU1wX8o",
        refresh_token:
          "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWNlM2FkOS1iZTE2LTRiNjgtOGRhYi1hYjA4YTVjMmZjZTkiLCJ0eXBlIjoicmYiLCJleHAiOjE2OTUyNTI2NTh9.a4wL9-XK_zyTyrXduBFgCsODFXrqiByVr5HOeiCbiQA",
        token_type: "bearer",
      };
      await route.fulfill({ json });
    });

    await page.goto("http://localhost:3000/");
    await page.waitForURL("http://localhost:3000/login");
    await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    await page.getByPlaceholder("Username").click();
    await page.getByPlaceholder("Username").fill("test");
    await page.getByPlaceholder("Password").click();
    await page.getByPlaceholder("Password").fill("test");
    await page.getByRole("button", { name: "Sign in" }).click();
  });
});
