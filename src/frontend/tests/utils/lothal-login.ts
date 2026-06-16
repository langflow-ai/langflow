import { expect, type Page } from "@playwright/test";

// Sign in through the real Lothal login page against a real auto-login-off
// backend (LANGFLOW_AUTO_LOGIN=false). The shared superuser the backend
// provisions from LANGFLOW_SUPERUSER/LANGFLOW_SUPERUSER_PASSWORD is langflow /
// langflow. With no explicit ?redirect the login page defaults its post-login
// destination to /lothal. No mocking — this drives the real auth flow.
export const loginAsSuperuser = async (page: Page) => {
  await page.goto("/login");
  await expect(page.getByText("Welcome back")).toBeVisible({ timeout: 30000 });
  await page.getByPlaceholder("Your username").fill("langflow");
  await page.getByPlaceholder("Your password").fill("langflow");

  const loginResponse = page.waitForResponse(
    (r) => r.url().includes("/api/v1/login") && r.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await loginResponse;

  await page.waitForURL("**/lothal", { timeout: 30000 });
};

// Delete every project the signed-in user owns, via the real API (the browser
// context's session cookie authorizes the request). Gives the dashboard tests a
// clean slate without mocking the project list.
export const deleteAllProjects = async (page: Page) => {
  const res = await page.request.get("/api/v1/lothal/projects/");
  if (!res.ok()) return;
  const projects = (await res.json()) as Array<{ id: string }>;
  for (const p of projects) {
    await page.request.delete(`/api/v1/lothal/projects/${p.id}`);
  }
};
