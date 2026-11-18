import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IntegrationProviderRead } from "@/controllers/API/queries/connections";
import { axe } from "@/utils/a11y-test";
import ProviderSelect from "../components/ProviderSelect";
import { selectProvider } from "./provider-select-utils";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`provider-icon-${name}`} aria-hidden="true" />
  ),
}));

const providers = [
  { provider_id: "servicenow", display_name: "ServiceNow", icon: "ServiceNow" },
  { provider_id: "google", display_name: "Google", icon: "Google" },
] as IntegrationProviderRead[];

it("names the provider field and displays catalog icons in the list", async () => {
  const onChange = jest.fn();
  const { container } = render(
    <ProviderSelect
      providers={providers}
      value="servicenow"
      onChange={onChange}
    />,
  );
  const trigger = screen.getByRole("combobox", { name: "Provider" });
  expect(within(trigger).getByTestId("provider-icon-ServiceNow")).toBeVisible();
  expect(await axe(container)).toHaveNoViolations();
  const user = userEvent.setup();
  await user.click(trigger);
  expect(
    within(screen.getByRole("option", { name: "ServiceNow" })).getByTestId(
      "provider-icon-ServiceNow",
    ),
  ).toBeVisible();
  expect(
    within(screen.getByRole("option", { name: "Google" })).getByTestId(
      "provider-icon-Google",
    ),
  ).toBeVisible();
  await user.keyboard("{Escape}");
  await selectProvider(user, "Google");
  expect(onChange).toHaveBeenCalledWith("google");
});
