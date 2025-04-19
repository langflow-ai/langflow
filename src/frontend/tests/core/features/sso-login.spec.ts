import { expect, test } from "@playwright/test";

// Skip this test if SSO is not enabled
const ssoTestEnabled = process.env.LANGFLOW_SSO_TEST_ENABLED === "true";

// Validate that the required environment variables are set
const validateEnvVars = () => {
  const requiredEnvVars = [
    "LANGFLOW_SSO_TEST_REGULAR_USER_USERNAME",
    "LANGFLOW_SSO_TEST_REGULAR_USER_PASSWORD",
    "LANGFLOW_SSO_TEST_ADMIN_USER_USERNAME",
    "LANGFLOW_SSO_TEST_ADMIN_USER_PASSWORD",
  ];

  const missingEnvVars = requiredEnvVars.filter(
    (envVar) => !process.env[envVar],
  );
  if (missingEnvVars.length > 0) {
    throw new Error(
      `The following environment variables are required for this test: ${missingEnvVars.join(", ")}`,
    );
  }
};

// Define a type for the SSO user
type SSOUser = {
  type: "regular" | "admin";
  username: string;
  password: string;
};

// Define a function to preform the SSO login
const preformLogin = async (page, user: SSOUser) => {
  console.log(
    `Attempting SSO login with ${user.type} as user:${user.username}`,
  );

  // Navigate to the home page
  await page.goto("/");

  // Ensure the SSO login button is visible
  const ssoButton = page.getByRole("button", { name: "Sign in with SSO" });
  await expect(ssoButton).toBeVisible();
  ssoButton.click();

  // Wait for the Keycloak login page to load
  await page.waitForLoadState();

  try {
    // Ensure the Keycloak login page is visible
    const usernameInput = page.getByTestId("form-input-username");
    await expect(usernameInput).toBeVisible();
    usernameInput.click();
    usernameInput.fill(user.username || "");

    const passwordInput = page.getByTestId("form-input-password");
    await expect(passwordInput).toBeVisible();
    passwordInput.click();
    passwordInput.fill(user.password || "");

    // Click the login button
    await page.getByTestId("login-btn").click();

    // Wait for the user to be redirected back to the home page
    await page.waitForLoadState();

    // Check if we are logged in
    const userMenuButton = page.getByTestId("user_menu_button");
    await expect(userMenuButton).toBeVisible();

    console.log(`Successfully logged in as ${user.type} user:${user.username}`);

    return true;
  } catch (error) {
    console.error("Error during SSO login:", error.message);

    // Take a screenshot of the login failure
    await page.screenshot({
      path: `sso-login-failure-${user.type}-${new Date().toISOString()}.png`,
    });

    throw error;
  }
};

// Define a function to preform the SSO logout
const preformLogout = async (page) => {
  try {
    // Logout the user
    await page.getByTestId("user_menu_button").click();
    await page.getByRole("menuitem", { name: "Logout" }).click();

    // Check if the SSO login button is visible
    const ssoButton = page.getByRole("button", { name: "Sign in with SSO" });
    await expect(ssoButton).toBeVisible();

    console.log("Successfully logged out");

    return true;
  } catch (error) {
    console.error("Error during SSO logout:", error.message);

    // Take a screenshot of the logout failure
    await page.screenshot({
      path: `sso-logout-failure-${new Date().toISOString()}.png`,
    });

    throw error;
  }
};

test.describe("SSO Authentication", () => {
  console.log(
    "LANGFLOW_SSO_TEST_ENABLED:",
    process.env.LANGFLOW_SSO_TEST_ENABLED,
  );
  console.log("ssoTestEnabled variable:", ssoTestEnabled);
  // Skip the entire test suite if SSO tests are not enabled
  test.skip(
    !ssoTestEnabled,
    "LANGFLOW_SSO_TEST_ENABLED required to run this test and must be set to 'true'",
  );

  test.beforeAll(async ({ browser }) => {
    validateEnvVars();
  });

  test("Regular User Login with SSO", async ({ page }) => {
    const user: SSOUser = {
      type: "regular",
      username: process.env.LANGFLOW_SSO_TEST_REGULAR_USER_USERNAME!,
      password: process.env.LANGFLOW_SSO_TEST_REGULAR_USER_PASSWORD!,
    };

    // SSO Login with the regular user
    await preformLogin(page, user);

    // SSO Logout
    await preformLogout(page);
  });

  test("Admin User Login with SSO", async ({ page }) => {
    const user: SSOUser = {
      type: "admin",
      username: process.env.LANGFLOW_SSO_TEST_ADMIN_USER_USERNAME!,
      password: process.env.LANGFLOW_SSO_TEST_ADMIN_USER_PASSWORD!,
    };

    // SSO Login with the admin user
    await preformLogin(page, user);

    // SSO Logout
    await preformLogout(page);
  });

  test("Invalid User Login with SSO", async ({ page }) => {
    // Navigate to the home page
    await page.goto("/");

    // Ensure the SSO login button is visible
    const ssoButton = page.getByRole("button", { name: "Sign in with SSO" });
    await expect(ssoButton).toBeVisible();
    ssoButton.click();

    // Wait for the Keycloak login page to load
    await page.waitForLoadState();

    // Ensure the Keycloak login page is visible
    const usernameInput = page.getByTestId("form-input-username");
    await expect(usernameInput).toBeVisible();
    usernameInput.click();
    usernameInput.fill("invalid_username");

    const passwordInput = page.getByTestId("form-input-password");
    await expect(passwordInput).toBeVisible();
    passwordInput.click();
    passwordInput.fill("invalid_password");

    // Click the login button
    await page.getByTestId("login-btn").click();

    const errorMessage = page.getByText("Invalid username or password.");
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText("Invalid username or password.");
  });

  test("Validate Admin SSO User role", async ({ page }) => {
    const user: SSOUser = {
      type: "admin",
      username: process.env.LANGFLOW_SSO_TEST_ADMIN_USER_USERNAME!,
      password: process.env.LANGFLOW_SSO_TEST_ADMIN_USER_PASSWORD!,
    };

    // SSO Login with the admin user
    await preformLogin(page, user);

    // Navigate to the admin page
    await page.getByTestId("user_menu_button").click();
    await page.getByTestId("menu_admin_button").click();

    // Check New User button disabled
    await page.waitForSelector('button:has-text("New User")', {
      timeout: 30000,
    });

    const newUserButton = page.getByRole("button", { name: "New User" });
    expect(newUserButton).toBeDisabled();

    // Wait for user table to load
    await page.waitForSelector("table.w-full", { timeout: 30000 });
    const table = page.locator("table.w-full");
    expect(table).toBeVisible();

    // Check User list
    const userTableRows = table.locator("tbody tr");

    // Check if the admin user is in the user list
    const adminUserRow = userTableRows.filter({
      has: page.getByRole("cell", { name: `${user.username}` }),
    });

    const activeCell = adminUserRow.locator("td").nth(2);

    expect(activeCell).toContainText("Yes");

    const superUserCell = adminUserRow.locator("td").nth(3);

    expect(superUserCell).toContainText("Yes");

    const isKeycloakUserCell = adminUserRow.locator("td").nth(4);

    expect(isKeycloakUserCell).toContainText("Yes");

    const deletedCell = adminUserRow.locator("td").nth(5);

    expect(deletedCell).toContainText("No");

    const activeAtCell = adminUserRow.locator("td").nth(9);

    expect(activeAtCell).toContainText("");

    // Check lagnflow user
    const langflowUserRow = userTableRows.nth(0);

    const activeCellLG = langflowUserRow.locator("td").nth(2);

    expect(activeCellLG.locator("button")).toBeVisible();

    const superUserCellLG = langflowUserRow.locator("td").nth(3);

    expect(superUserCellLG.locator("button")).toBeVisible();

    const isKeycloakUserCellLG = langflowUserRow.locator("td").nth(4);

    expect(isKeycloakUserCellLG).toContainText("No");

    const deletedCellLG = langflowUserRow.locator("td").nth(5);

    expect(deletedCellLG).toContainText("No");

    const activeAtCellLG = langflowUserRow.locator("td").nth(9);

    expect(activeAtCellLG.locator("button")).toHaveCount(2);
  });
});
