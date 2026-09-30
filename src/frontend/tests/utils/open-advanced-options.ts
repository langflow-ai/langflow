import type { Page } from "@playwright/test";

/**
 * LE-1810 — the Inspector Panel is a parameter MANAGER: it lists every
 * manageable parameter with Add/Remove (canvas visibility) and an API
 * toggle (api_editable). Field values are edited ON THE NODE only; the old
 * editNodeModal toolbar trigger and the global inspector toggles are gone.
 *
 * The panel opens from the node toolbar "Parameters" button
 * (testid `parameters-button`) for the selected node.
 */

export const openParametersPanel = async (page: Page) => {
  if ((await page.getByTestId("inspection-panel-header").count()) === 0) {
    await page.getByTestId("parameters-button").click();
  }
  await page.getByTestId("inspection-panel-header").waitFor({
    state: "visible",
  });
};

export const closeParametersPanel = async (page: Page) => {
  if ((await page.getByTestId("inspection-panel-header").count()) > 0) {
    await page.getByTestId("inspection-panel-close").click();
    await page.getByTestId("inspection-panel-header").waitFor({
      state: "hidden",
    });
  }
};

/** Adds a hidden parameter to the node (panel row "+ Add"). */
export const addParameterToNode = async (page: Page, name: string) => {
  await openParametersPanel(page);
  await page.getByTestId(`inspector-add-${name}`).click();
};

/** Removes a parameter from the node (panel row "Remove"). */
export const removeParameterFromNode = async (page: Page, name: string) => {
  await openParametersPanel(page);
  await page.getByTestId(`inspector-remove-${name}`).click();
};

/** Toggles a parameter between on-node and hidden, whichever applies. */
export const toggleParameterOnNode = async (page: Page, name: string) => {
  await openParametersPanel(page);
  const addButton = page.getByTestId(`inspector-add-${name}`);
  if ((await addButton.count()) > 0) {
    await addButton.click();
    return;
  }
  await page.getByTestId(`inspector-remove-${name}`).click();
};

/** Sets the api_editable state of a parameter through the panel API toggle. */
export const setParameterApiEditable = async (
  page: Page,
  name: string,
  enabled: boolean,
) => {
  await openParametersPanel(page);
  const apiButton = page.getByTestId(`inspector-api-${name}`);
  const isPressed = (await apiButton.getAttribute("aria-pressed")) === "true";
  if (isPressed !== enabled) {
    await apiButton.click();
  }
};

/** @deprecated LE-1810 — use openParametersPanel (values are edited on the node). */
export const openAdvancedOptions = async (
  page: Page,
  _skipEnableFields = false,
) => {
  await openParametersPanel(page);
};

/** @deprecated LE-1810 — use closeParametersPanel. */
export const closeAdvancedOptions = async (
  page: Page,
  _skipEnableFields = false,
) => {
  await closeParametersPanel(page);
};

/** @deprecated LE-1810 — the global inspector toggle no longer exists. */
export const enableInspectPanel = async (page: Page) => {
  await openParametersPanel(page);
};

/** @deprecated LE-1810 — the global inspector toggle no longer exists. */
export const disableInspectPanel = async (page: Page) => {
  await closeParametersPanel(page);
};
