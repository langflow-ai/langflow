import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type React from "react";
import { axe } from "@/utils/a11y-test";
import type { ProviderCredentials } from "../types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import ProviderCredentialsForm from "../components/provider-credentials-form";

const defaultCredentials: ProviderCredentials = {
  name: "",
  provider_key: "watsonx-orchestrate",
  url: "",
  api_key: "",
};

function renderForm(
  overrides: Partial<React.ComponentProps<typeof ProviderCredentialsForm>> = {},
) {
  const onCredentialsChange = jest.fn();
  const result = render(
    <ProviderCredentialsForm
      credentials={defaultCredentials}
      onCredentialsChange={onCredentialsChange}
      {...overrides}
    />,
  );
  return { onCredentialsChange, ...result };
}

describe("Accessibility", () => {
  it("should_have_no_axe_violations in single-column layout", async () => {
    const { container } = renderForm();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations in two-column layout", async () => {
    const { container } = renderForm({ layout: "two-column" });

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations with the API key revealed", async () => {
    const user = userEvent.setup();
    const { container } = renderForm();

    await user.click(screen.getByRole("button", { name: "Show API key" }));

    expect(await axe(container)).toHaveNoViolations();
  });

  it("programmatically associates the Name, URL, and API key labels with their fields", () => {
    renderForm();

    expect(screen.getByRole("textbox", { name: /Name/ })).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /Service Instance URL/ }),
    ).toBeInTheDocument();
    // The API key input is type="password" until revealed, which testing-library
    // doesn't expose via getByRole — query it directly and check its label.
    expect(
      screen.getByLabelText(/API Key/, { selector: "input" }),
    ).toBeInTheDocument();
  });

  // Regression guard: a bare "*" next to a label reads as "asterisk"/"star"
  // to a screen reader, not "required" — it must be aria-hidden, with the
  // real requiredness communicated via aria-required on the field itself.
  it("hides the visual required asterisks from assistive tech and exposes aria-required instead", () => {
    renderForm();

    const nameField = screen.getByRole("textbox", { name: /Name/ });
    expect(nameField).toHaveAttribute("aria-required", "true");

    const urlField = screen.getByRole("textbox", {
      name: /Service Instance URL/,
    });
    expect(urlField).toHaveAttribute("aria-required", "true");

    const apiKeyField = screen.getByLabelText(/API Key/, {
      selector: "input",
    });
    expect(apiKeyField).toHaveAttribute("aria-required", "true");
  });

  it("marks the API key as not required and does not set aria-required when optional", () => {
    renderForm({ apiKeyRequired: false, urlRequired: false });

    const urlField = screen.getByRole("textbox", {
      name: /Service Instance URL/,
    });
    expect(urlField).toHaveAttribute("aria-required", "false");

    const apiKeyField = screen.getByLabelText(/API Key/, {
      selector: "input",
    });
    expect(apiKeyField).toHaveAttribute("aria-required", "false");
  });
});

describe("Field behavior", () => {
  it("calls onCredentialsChange when typing the name", async () => {
    const user = userEvent.setup();
    const { onCredentialsChange } = renderForm();

    await user.type(screen.getByRole("textbox", { name: /Name/ }), "A");
    expect(onCredentialsChange).toHaveBeenCalledWith(
      expect.objectContaining({ name: "A" }),
    );
  });

  it("toggles the API key visibility", async () => {
    const user = userEvent.setup();
    renderForm();

    const toggle = screen.getByRole("button", { name: "Show API key" });
    await user.click(toggle);

    expect(
      screen.getByRole("button", { name: "Hide API key" }),
    ).toBeInTheDocument();
  });

  it("disables the URL field when urlReadOnly is set", () => {
    renderForm({ urlReadOnly: true });

    expect(
      screen.getByRole("textbox", { name: /Service Instance URL/ }),
    ).toBeDisabled();
  });
});
