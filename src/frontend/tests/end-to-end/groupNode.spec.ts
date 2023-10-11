import { expect, test } from "@playwright/test";

test.describe("Group component tests", () => {
  test("group test", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page
      .locator(
        "div:nth-child(7) > div:nth-child(2) > .card-component-footer-arrangement > .inline-flex"
      )
      .click();
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]/div"
      )
      .click({
        modifiers: ["Control"],
      });
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div"
      )
      .click({
        modifiers: ["Control"],
      });
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div[3]/div/div[1]/div"
      )
      .click({
        modifiers: ["Control"],
      });
    await page.getByRole("button", { name: "Group" }).click();
    expect(
      await page
        .locator(
          "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div/div"
        )
        .isVisible()
    ).toBeTruthy();
    await page.getByPlaceholder("Type something...").first().click();
    await page.getByPlaceholder("Type something...").first().fill("test");
    await page.locator(".side-bar-buttons-arrangement").click();
    expect(
      await page
        .locator(
          "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div/div/div[2]/div/div/div[1]/div/div[1]/div/div"
        )
        .textContent()
    ).toBe("test");
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div/div"
      )
      .locator('input[type="text"]')
      .click();
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div/div"
      )
      .locator('input[type="text"]')
      .fill("fieldValue");
    await page.locator(".side-bar-buttons-arrangement").click();
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div"
      )
      .click();

    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[2]/div/span/button[3]/div/div"
      )
      .click();
    await page.getByLabel("Edit").click();
    await page
      .getByRole("button", { name: "zero-shot-react-description" })
      .click();
    await page.getByText("openai-functions").click();
    await page.getByRole("button", { name: "Save Changes" }).click();
    await page
      .locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div[2]/div/span/button[3]/div/div"
      )
      .click();
    await page.getByLabel("Ungroup").click();
    await expect(
      page.locator(
        "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div/div/div[2]/div[3]/div/div[2]/div[4]/div/div[2]/div/input"
      )
    ).toHaveValue("fieldValue");
    expect(
      await page
        .locator(
          "//html/body/div/div/div[2]/div/main/div/div/div/div[1]/div[1]/div/div/div[2]/div[2]/div/div[2]/div[5]/div/div[2]/div/button/span[1]"
        )
        .textContent()
    ).toBe("openai-functions");
  });
});
