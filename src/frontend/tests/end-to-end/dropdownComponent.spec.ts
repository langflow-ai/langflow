import { expect, test } from "@playwright/test";

test("dropDownComponent", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("amazon");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsAmazon Bedrock")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTestId("title-Amazon Bedrock").click();

  await page.getByTestId("dropdown-model_id").click();

  await page.getByTestId("ai21.j2-mid-v1-10-option").click();

  let value = await page
    .getByTestId("value-dropdown-dropdown-model_id")
    .first()
    .innerText();
  if (value !== "ai21.j2-mid-v1") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("dropdown-model_id").click();
  await page.getByTestId("anthropic.claude-v2:1-6-option").click();

  value = await page.getByTestId("dropdown-model_id").innerText();
  if (value !== "anthropic.claude-v2:1") {
    expect(false).toBeTruthy();
  }

  await page.waitForTimeout(1000);

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  value = await page.getByTestId("dropdown-edit-model_id").innerText();
  if (value !== "anthropic.claude-v2:1") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showcredentials_profile_name"]').click();
  expect(
    await page.locator('//*[@id="showcredentials_profile_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showcredentials_profile_name"]').click();
  expect(
    await page.locator('//*[@id="showcredentials_profile_name"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showendpoint_url"]').click();
  expect(
    await page.locator('//*[@id="showendpoint_url"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showendpoint_url"]').click();
  expect(
    await page.locator('//*[@id="showendpoint_url"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showregion_name"]').click();
  expect(
    await page.locator('//*[@id="showregion_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showregion_name"]').click();
  expect(
    await page.locator('//*[@id="showregion_name"]').isChecked(),
  ).toBeTruthy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(await page.locator('//*[@id="showmodel_id"]').isChecked()).toBeFalsy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(
    await page.locator('//*[@id="showmodel_id"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showcredentials_profile_name"]').click();
  expect(
    await page.locator('//*[@id="showcredentials_profile_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showcredentials_profile_name"]').click();
  expect(
    await page.locator('//*[@id="showcredentials_profile_name"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showendpoint_url"]').click();
  expect(
    await page.locator('//*[@id="showendpoint_url"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showendpoint_url"]').click();
  expect(
    await page.locator('//*[@id="showendpoint_url"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showregion_name"]').click();
  expect(
    await page.locator('//*[@id="showregion_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showregion_name"]').click();
  expect(
    await page.locator('//*[@id="showregion_name"]').isChecked(),
  ).toBeTruthy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(await page.locator('//*[@id="showmodel_id"]').isChecked()).toBeFalsy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(
    await page.locator('//*[@id="showmodel_id"]').isChecked(),
  ).toBeTruthy();

  await page.getByTestId("dropdown-edit-model_id").click();
  await page.getByTestId("ai21.j2-mid-v1-10-option").click();

  value = await page.getByTestId("dropdown-edit-model_id").innerText();
  if (value !== "ai21.j2-mid-v1") {
    expect(false).toBeTruthy();
  }

  await page.getByText("Save Changes", { exact: true }).click();

  value = await page.getByTestId("dropdown-model_id").innerText();
  if (value !== "ai21.j2-mid-v1") {
    expect(false).toBeTruthy();
  }
  await page.getByTestId("code-button-modal").click();
  await page
    .locator("#CodeEditor div")
    .filter({ hasText: "from typing import" })
    .nth(1)
    .click();
  await page.locator("textarea").press("Control+a");
  const emptyOptionsCode = `from typing import Optional
from langflow.field_typing import BaseLanguageModel
from langchain_community.llms.bedrock import Bedrock

from langflow.interface.custom.custom_component import CustomComponent


class AmazonBedrockComponent(CustomComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "LLM model from Amazon Bedrock."
    icon = "Amazon"

    def build_config(self):
        return {
            "model_id": {
                "display_name": "Model Id",
                "options": [],
            },
            "credentials_profile_name": {"display_name": "Credentials Profile Name"},
            "streaming": {"display_name": "Streaming", "field_type": "bool"},
            "endpoint_url": {"display_name": "Endpoint URL"},
            "region_name": {"display_name": "Region Name"},
            "model_kwargs": {"display_name": "Model Kwargs"},
            "cache": {"display_name": "Cache"},
            "code": {"advanced": True},
        }

    def build(
        self,
        model_id: str = "anthropic.claude-instant-v1",
        credentials_profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        endpoint_url: Optional[str] = None,
        streaming: bool = False,
        cache: Optional[bool] = None,
    ) -> BaseLanguageModel:
        try:
            output = Bedrock(
                credentials_profile_name=credentials_profile_name,
                model_id=model_id,
                region_name=region_name,
                model_kwargs=model_kwargs,
                endpoint_url=endpoint_url,
                streaming=streaming,
                cache=cache,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e
        return output

  `;
  await page.locator("textarea").fill(emptyOptionsCode);
  await page.getByRole("button", { name: "Check & Save" }).click();
  await page.getByText("No parameters are available for display.").isVisible();
});
