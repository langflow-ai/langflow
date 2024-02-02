import { test } from "@playwright/test";

test.describe("Login Tests", () => {
  test("Login_Success", async ({ page }) => {
    //   await page.route("**/api/v1/login", async (route) => {
    //     const json = {
    //       access_token:
    //         "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWNlM2FkOS1iZTE2LTRiNjgtOGRhYi1hYjA4YTVjMmZjZTkiLCJleHAiOjE2OTUyNTIwNTh9.MBYFwMhTcZnsW_L7p4qavUhSDylCllJQWUCJdU1wX8o",
    //       refresh_token:
    //         "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWNlM2FkOS1iZTE2LTRiNjgtOGRhYi1hYjA4YTVjMmZjZTkiLCJ0eXBlIjoicmYiLCJleHAiOjE2OTUyNTI2NTh9.a4wL9-XK_zyTyrXduBFgCsODFXrqiByVr5HOeiCbiQA",
    //       token_type: "bearer",
    //     };
    //     await route.fulfill({ json });
    //   });
    //   await page.goto("http://localhost:3000/");
    //   await page.waitForURL("http://localhost:3000/login");
    //   await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    //   await page.getByPlaceholder("Username").click();
    //   await page.getByPlaceholder("Username").fill("test");
    //   await page.getByPlaceholder("Password").click();
    //   await page.getByPlaceholder("Password").fill("test");
    //   await page.getByRole("button", { name: "Sign in" }).click();
    //   await page.getByRole("button", { name: "Community Examples" }).click();
    //   await page.waitForSelector(".community-pages-flows-panel");
    //   expect(
    //     await page
    //       .locator(".community-pages-flows-panel")
    //       .evaluate((el) => el.children)
    //   ).toBeTruthy();
    // });
    // test("Login Error", async ({ page }) => {
    //   await page.route("**/api/v1/login", async (route) => {
    //     const json = { detail: "Incorrect username or password" };
    //     await route.fulfill({ json, status: 401 });
    //   });
    //   await page.goto("http://localhost:3000/");
    //   await page.waitForURL("http://localhost:3000/login");
    //   await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    //   await page.getByPlaceholder("Username").click();
    //   await page.getByPlaceholder("Username").fill("test");
    //   await page.getByPlaceholder("Password").click();
    //   await page.getByPlaceholder("Password").fill("test5");
    //   await page.getByRole("button", { name: "Sign in" }).click();
    //   await page.getByRole("heading", { name: "Error signing in" }).click();
    // });
    // test("Login create account wrong form", async ({ page }) => {
    //   const fullfillForm = async (username, password, confirmPassword) => {
    //     await page.getByPlaceholder("Username").click();
    //     await page.getByPlaceholder("Username").fill(username);
    //     await page.getByPlaceholder("Password", { exact: true }).click();
    //     await page.getByPlaceholder("Password", { exact: true }).fill(password);
    //     await page.getByPlaceholder("Confirm your password").click();
    //     await page
    //       .getByPlaceholder("Confirm your password")
    //       .fill(confirmPassword);
    //   };
    //   await page.goto("http://localhost:3000/");
    //   await page.waitForURL("http://localhost:3000/login");
    //   await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    //   await page
    //     .getByRole("button", { name: "Don't have an account? Sign Up" })
    //     .click();
    //   await page.getByText("Sign up to Langflow").click();
    //   await page.goto("http://localhost:3000/signup");
    //   await page.getByText("Sign up to Langflow").click();
    //   await fullfillForm("name", "vazz", "vazz5");
    //   expect(
    //     await page.getByRole("button", { name: "Sign up" }).isDisabled()
    //   ).toBeTruthy();
    //   await fullfillForm("", "vazz", "vazz");
    //   expect(
    //     await page.getByRole("button", { name: "Sign up" }).isDisabled()
    //   ).toBeTruthy();
    //   await fullfillForm("name", "", "");
    //   expect(
    //     await page.getByRole("button", { name: "Sign up" }).isDisabled()
    //   ).toBeTruthy();
    //   await fullfillForm("", "", "");
    //   expect(
    //     await page.getByRole("button", { name: "Sign up" }).isDisabled()
    //   ).toBeTruthy();
    // });
    // test("Login create account success", async ({ page }) => {
    //   await page.route("**/api/v1/users/", async (route) => {
    //     const json = {
    //       id: "e9ac1bdc-429b-475d-ac03-d26f9a2a3210",
    //       username: "teste",
    //       profile_image: null,
    //       is_active: false,
    //       is_superuser: false,
    //       create_at: "2023-09-21T01:45:51.873303",
    //       updated_at: "2023-09-21T01:45:51.873305",
    //       last_login_at: null,
    //     };
    //     await route.fulfill({ json, status: 201 });
    //   });
    //   const submitForm = async (username, password, confirmPassword) => {
    //     await page.getByPlaceholder("Username").click();
    //     await page.getByPlaceholder("Username").fill(username);
    //     await page.getByPlaceholder("Password", { exact: true }).click();
    //     await page.getByPlaceholder("Password", { exact: true }).fill(password);
    //     await page.getByPlaceholder("Confirm your password").click();
    //     await page
    //       .getByPlaceholder("Confirm your password")
    //       .fill(confirmPassword);
    //   };
    //   await page.goto("http://localhost:3000/");
    //   await page.waitForURL("http://localhost:3000/login");
    //   await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    //   await page
    //     .getByRole("button", { name: "Don't have an account? Sign Up" })
    //     .click();
    //   await page.getByText("Sign up to Langflow").click();
    //   await page.goto("http://localhost:3000/signup");
    //   await page.getByText("Sign up to Langflow").click();
    //   await submitForm("teste", "pass", "pass");
    //   await page.getByRole("button", { name: "Sign up" }).click();
    //   await page.waitForURL("http://localhost:3000/login", { timeout: 1000 });
    //   await page.getByText("Account created! Await admin activation.").click();
  });
});
