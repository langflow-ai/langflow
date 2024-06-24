export const custom = `from langflow.custom import CustomComponent

from langflow.field_typing import BaseLanguageModel
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document
from langflow.field_typing import NestedDict

import requests

class YourComponent(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return { "file": { "file_type": ["json"], } }

    def build(self, url: str,file:str,integer:int,nested:NestedDict,flt:float,boolean:bool,lisst:list[str],dictionary:dict, llm: BaseLanguageModel, prompt: PromptTemplate) -> Document:

        return "test"`;

export const offsetElements = async ({
  sourceElement,
  targetElement,
  page,
}) => {
  // Get bounding boxes
  const box1 = await sourceElement.boundingBox();
  const box2 = await targetElement.boundingBox();

  await page.mouse.move((box2?.x || 0) + 5, (box2?.y || 0) + 5);
  await page.mouse.down();

  // Move to the right of the source element
  await page.mouse.move(
    (box2?.x || 0) + (box2?.width || 0) / 2 + (box1?.width || 0),
    box2?.y || 0,
  );
  await page.mouse.up();
};

export const focusElementsOnBoard = async ({ page }) => {
  const focusElements = await page.locator(
    '//*[@id="react-flow-id"]/div/div[2]/button[3]',
  );
  focusElements.click();
};
