import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import InputComponent from "../index";

const renderPasswordInput = () =>
  render(
    <InputComponent
      id="password-input"
      password={true}
      value=""
      placeholder="Enter password"
      onChange={() => {}}
    />,
  );

const getToggleButton = (container: HTMLElement) =>
  container.querySelector<HTMLButtonElement>("button[type='button']");

describe("InputComponent password toggle accessibility", () => {
  it("should_render_password_input_with_toggle", () => {
    const { container } = renderPasswordInput();

    expect(container.querySelector("input")).not.toBeNull();
    expect(getToggleButton(container)).not.toBeNull();
  });

  // Known gap (a11y-action-plan 1.1): the show/hide toggle has
  // tabIndex={-1}, no aria-label, and no aria-pressed state.
  it("should_keep_toggle_in_tab_order", () => {
    const { container } = renderPasswordInput();

    const toggle = getToggleButton(container);
    expect(toggle).not.toBeNull();
    expect(toggle).not.toHaveAttribute("tabindex", "-1");
  });

  it("should_name_toggle_with_current_state", () => {
    const { container } = renderPasswordInput();

    const toggle = getToggleButton(container);
    expect(toggle).not.toBeNull();
    expect(toggle).toHaveAccessibleName(/show|hide/i);
    expect(toggle).toHaveAttribute("aria-pressed");
  });
});

describe("InputComponent field-label wiring", () => {
  // Regression guard: InputComponent has three mutually-exclusive render
  // branches (plain form input, object-options popover, options popover).
  // Only the options-popover branch applied ariaLabelledBy — the other two
  // silently dropped it, found while auditing this widget for the ticket
  // that added label wiring across the other ~30 field types.
  it("uses the field's real label on the plain form-input branch (isForm)", () => {
    render(
      <>
        <span id="field-label">API key</span>
        <InputComponent
          id="form-input"
          password={false}
          isForm
          value=""
          placeholder="Type something"
          onChange={() => {}}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "API key" }),
    ).toBeInTheDocument();
  });

  it("uses the field's real label on the object-options branch (isObjectOption)", () => {
    render(
      <>
        <span id="field-label">Linked flow</span>
        <InputComponent
          id="object-option-input"
          password={false}
          isObjectOption
          objectOptions={[{ name: "Flow A", id: "flow-a" }]}
          selectedOption=""
          setSelectedOption={() => {}}
          value=""
          placeholder="Select a flow"
          onChange={() => {}}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Linked flow" }),
    ).toBeInTheDocument();
  });

  it("should_have_no_axe_violations_on_the_plain_form_input_branch", async () => {
    const { container } = render(
      <>
        <span id="field-label">API key</span>
        <InputComponent
          id="form-input"
          password={false}
          isForm
          value=""
          placeholder="Type something"
          onChange={() => {}}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_on_the_object_options_branch", async () => {
    const { container } = render(
      <>
        <span id="field-label">Linked flow</span>
        <InputComponent
          id="object-option-input"
          password={false}
          isObjectOption
          objectOptions={[{ name: "Flow A", id: "flow-a" }]}
          selectedOption=""
          setSelectedOption={() => {}}
          value=""
          placeholder="Select a flow"
          onChange={() => {}}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
