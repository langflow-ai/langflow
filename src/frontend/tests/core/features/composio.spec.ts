import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";

const LOOPBACK_COMPOSIO_GMAIL_CODE = `
import pandas as pd
from lfx.custom import Component
from lfx.inputs.inputs import AuthInput, SecretStrInput, SortableListInput, TabInput
from lfx.io import Output
from lfx.schema import DataFrame


class ComposioGmailAPIComponent(Component):
    display_name = "Gmail"
    description = "Deterministic Composio Gmail fixture for Playwright."
    icon = "Gmail"
    inputs = [
        SecretStrInput(name="api_key", display_name="Composio API Key", required=True),
        TabInput(
            name="auth_mode",
            display_name="Auth Mode",
            options=["OAUTH2"],
            value="OAUTH2",
        ),
        AuthInput(
            name="auth_link",
            value="validated",
            auth_tooltip="Disconnect",
            show=True,
        ),
        SortableListInput(
            name="action_button",
            display_name="Action",
            placeholder="Select action",
            options=[{"name": "Fetch Emails", "icon": "Gmail"}],
            value="",
            limit=1,
        ),
    ]
    outputs = [Output(name="dataFrame", display_name="Table", method="as_dataframe")]

    def as_dataframe(self) -> DataFrame:
        return DataFrame(pd.DataFrame([
            {
                "marker": "LOOPBACK_COMPOSIO_GMAIL_USED",
                "subject": "Deterministic CI message",
                "sender": "fixture@example.test",
            }
        ]))
`;

test(
  "user should be able to configure and run a deterministic Composio Gmail action",
  { tag: ["@release", "@workspace", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-custom-component-button").click();
    await adjustScreenView(page, { numberOfZoomOut: 1 });
    await page.getByTestId("title-Custom Component").first().click();
    await page.getByTestId("code-button-modal").last().click();
    await page.locator("textarea").last().press("ControlOrMeta+a");
    await page.locator("textarea").last().fill(LOOPBACK_COMPOSIO_GMAIL_CODE);

    const customComponentResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith("/api/v1/custom_component"),
    );
    await page.getByTestId("checkAndSaveBtn").click();
    expect((await customComponentResponse).ok()).toBeTruthy();

    await expect(page.getByTestId("title-Gmail")).toBeVisible();
    await adjustScreenView(page, { numberOfZoomOut: 1 });
    const loopbackApiKeyInput = page.getByTestId(
      "popover-anchor-input-api_key",
    );
    await expect(loopbackApiKeyInput).toBeVisible();
    await expect(loopbackApiKeyInput).toHaveAttribute("type", "password");
    await expect(
      page.getByTestId(
        "button_open_list_selection_sortablelist_sortablelist_action_button",
      ),
    ).toBeVisible();
    await expect(page.getByTestId("button_connected_gmail")).toBeVisible();
    await expect(page.getByText("OAUTH2", { exact: true })).toBeVisible();

    await loopbackApiKeyInput.fill("langflow-composio-loopback-key"); // pragma: allowlist secret
    const actionButton = page.getByTestId(
      "button_open_list_selection_sortablelist_sortablelist_action_button",
    );
    await actionButton.click();
    const fetchEmails = page.getByTestId("list_item_fetch_emails");
    await expect(fetchEmails).toBeVisible();
    await fetchEmails.click();
    await expect(
      page
        .getByRole("application", { name: "Gmail node" })
        .getByText("Fetch Emails", { exact: true }),
    ).toBeVisible();

    await page.getByTestId("button_run_gmail").click();
    await expect(page.getByText(TEXTS.toastBuiltSuccessfully)).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByTestId("output-inspection-table-composiogmailapicomponent")
      .click();
    await expect(
      page.getByRole("gridcell", { name: "LOOPBACK_COMPOSIO_GMAIL_USED" }),
    ).toBeVisible();
    expect(await page.getByRole("gridcell").count()).toBeGreaterThan(1);
  },
);
