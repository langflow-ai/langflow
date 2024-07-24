import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("user must be able to freeze a path", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  //   const codeOpenAI = `
  // import operator
  // from functools import reduce

  // from langchain_openai import ChatOpenAI
  // from pydantic.v1 import SecretStr

  // from langflow.base.constants import STREAM_INFO_TEXT
  // from langflow.base.models.model import LCModelComponent
  // from langflow.base.models.openai_constants import MODEL_NAMES
  // from langflow.field_typing import LanguageModel
  // from langflow.inputs import (
  //     BoolInput,
  //     DictInput,
  //     DropdownInput,
  //     FloatInput,
  //     IntInput,
  //     MessageInput,
  //     SecretStrInput,
  //     StrInput,
  // )

  // class OpenAIModelComponent(LCModelComponent):
  //     display_name = "OpenAI"
  //     description = "Generates text using OpenAI LLMs."
  //     icon = "OpenAI"
  //     name = "OpenAIModel"

  //     inputs = [
  //         MessageInput(name="input_value", display_name="Input"),
  //         IntInput(
  //             name="max_tokens",
  //             display_name="Max Tokens",
  //             advanced=True,
  //             info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
  //         ),
  //         DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
  //         BoolInput(
  //             name="json_mode",
  //             display_name="JSON Mode",
  //             advanced=True,
  //             info="If True, it will output JSON regardless of passing a schema.",
  //         ),
  //         DictInput(
  //             name="output_schema",
  //             is_list=True,
  //             display_name="Schema",
  //             advanced=True,
  //             info="The schema for the Output of the model. You must pass the word JSON in the prompt. If left blank, JSON mode will be disabled.",
  //         ),
  //         DropdownInput(
  //             name="model_name", display_name="Model Name", advanced=False, options=MODEL_NAMES, value=MODEL_NAMES[0]
  //         ),
  //         StrInput(
  //             name="openai_api_base",
  //             display_name="OpenAI API Base",
  //             advanced=True,
  //             info="The base URL of the OpenAI API. Defaults to https://api.openai.com/v1. You can change this to use other APIs like JinaChat, LocalAI and Prem.",
  //         ),
  //         SecretStrInput(
  //             name="api_key",
  //             display_name="OpenAI API Key",
  //             info="The OpenAI API Key to use for the OpenAI model.",
  //             advanced=False,
  //             value="OPENAI_API_KEY",
  //         ),
  //         FloatInput(name="temperature", display_name="Temperature", value=0.1),
  //         BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
  //         StrInput(
  //             name="system_message",
  //             display_name="System Message",
  //             info="System message to pass to the model.",
  //             advanced=True,
  //         ),
  //         IntInput(
  //             name="seed",
  //             display_name="Seed",
  //             info="The seed controls the reproducibility of the job.",
  //             advanced=True,
  //             value=1,
  //         ),
  //     ]

  //     def build_model(self) -> LanguageModel:  # type: ignore[type-var]
  //         # self.output_schema is a list of dictionaries
  //         # let's convert it to a dictionary
  //         output_schema_dict: dict[str, str] = reduce(operator.ior, self.output_schema or {}, {})
  //         openai_api_key = self.api_key
  //         temperature = self.temperature
  //         model_name: str = self.model_name
  //         max_tokens = self.max_tokens
  //         model_kwargs = self.model_kwargs or {}
  //         openai_api_base = self.openai_api_base or "https://api.openai.com/v1"
  //         json_mode = bool(output_schema_dict) or self.json_mode
  //         seed = self.seed

  //         if openai_api_key:
  //             api_key = SecretStr(openai_api_key)
  //         else:
  //             api_key = None
  //         output = ChatOpenAI(
  //             max_tokens=max_tokens or None,
  //             model_kwargs=model_kwargs,
  //             model=model_name,
  //             base_url=openai_api_base,
  //             api_key=api_key,
  //             temperature=0.8,
  //             seed=seed,
  //         )
  //         if json_mode:
  //             if output_schema_dict:
  //                 output = output.with_structured_output(schema=output_schema_dict, method="json_mode")  # type: ignore
  //             else:
  //                 output = output.bind(response_format={"type": "json_object"})  # type: ignore

  //         return output  # type: ignore

  //     def _get_exception_message(self, e: Exception):
  //         """
  //         Get a message from an OpenAI exception.

  //         Args:
  //             exception (Exception): The exception to get the message from.

  //         Returns:
  //             str: The message from the exception.
  //         """

  //         try:
  //             from openai import BadRequestError
  //         except ImportError:
  //             return
  //         if isinstance(e, BadRequestError):
  //             message = e.body.get("message")  # type: ignore
  //             if message:
  //                 return message
  //         return

  //   `;

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

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

  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("textarea-input_value")
    .first()
    .fill(
      "say a random number between 1 and 100000 and a random animal that lives in the sea",
    );

  await page.getByTestId("dropdown-model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  // await page.getByText("OpenAI").first().click();

  // await page.getByTestId("code-button-modal").first().click();

  // await page.locator("textarea").press("Control+a");
  // await page.locator("textarea").fill(codeOpenAI);
  // await page.locator('//*[@id="checkAndSaveBtn"]').click();

  await page.waitForTimeout(2000);

  await page.getByTestId("float-input").fill("1.0");

  await page.waitForTimeout(2000);

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByTestId("output-inspection-text").first().click();

  const randomTextGeneratedByAI = await page
    .getByPlaceholder("Empty")
    .first()
    .inputValue();

  await page.getByText("Close").first().click();

  await page.waitForTimeout(3000);

  await page.getByTestId("float-input").fill("1.2");

  await page.waitForTimeout(2000);

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByTestId("output-inspection-text").first().click();

  const secondRandomTextGeneratedByAI = await page
    .getByPlaceholder("Empty")
    .first()
    .inputValue();

  await page.getByText("Close").first().click();

  await page.waitForTimeout(3000);

  await page.getByText("openai").first().click();

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-FreezeAll").click();

  await page.waitForTimeout(1000);

  expect(await page.getByTestId("icon-Snowflake").count()).toBeGreaterThan(0);

  await page.waitForTimeout(1000);
  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByTestId("output-inspection-text").first().click();

  const thirdRandomTextGeneratedByAI = await page
    .getByPlaceholder("Empty")
    .first()
    .inputValue();

  await page.getByText("Close").first().click();

  expect(randomTextGeneratedByAI).not.toEqual(secondRandomTextGeneratedByAI);
  expect(randomTextGeneratedByAI).not.toEqual(thirdRandomTextGeneratedByAI);
  expect(secondRandomTextGeneratedByAI).toEqual(thirdRandomTextGeneratedByAI);
});
