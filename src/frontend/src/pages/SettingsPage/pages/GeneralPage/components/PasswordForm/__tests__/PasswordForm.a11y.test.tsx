import { render, screen } from "@testing-library/react";
import PasswordFormComponent from "../index";

// Deliberately does NOT mock @radix-ui/react-form. Radix's own valueMissing →
// aria-describedby wiring cannot be exercised under jsdom (the slot props
// never materialize there), so that path is covered by the browser-side
// harness capture (evidence/3.3.1-form-errors, password-form--value-missing).
// What jsdom CAN pin: the serverError node's association contract and the
// fields' accessible names.

const renderForm = (serverError: string | null = null) =>
  render(
    <PasswordFormComponent
      currentPassword=""
      password=""
      cnfPassword=""
      handleInput={jest.fn()}
      handlePatchPassword={jest.fn()}
      serverError={serverError}
    />,
  );

const getInputs = () => [
  screen.getByPlaceholderText("Current Password"),
  screen.getByPlaceholderText("Password"),
  screen.getByPlaceholderText("Confirm Password"),
];

describe("PasswordForm accessibility", () => {
  it("associates_a_server_error_with_all_three_fields", () => {
    renderForm("Passwords do not match");

    const error = screen.getByText("Passwords do not match");
    expect(error).toHaveAttribute("role", "alert");
    expect(error).toHaveAttribute("id", "password-form-error");

    for (const input of getInputs()) {
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(input).toHaveAttribute("aria-describedby", "password-form-error");
    }
  });

  it("emits_no_aria_error_keys_without_a_server_error", () => {
    // Companion to the clobber fix: without a server error the DOM must be
    // clean of error wiring. The clobber itself (a present-but-undefined
    // aria-describedby key overriding Radix's Slot-provided value) is only
    // observable in a real browser — see the harness capture noted above.
    renderForm(null);

    for (const input of getInputs()) {
      expect(input).not.toHaveAttribute("aria-invalid");
      expect(input).not.toHaveAttribute("aria-describedby");
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("names_the_placeholder_only_fields", () => {
    renderForm(null);

    expect(
      screen.getByLabelText("Current Password", { selector: "input" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Password", { selector: "input" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Confirm Password", { selector: "input" }),
    ).toBeInTheDocument();
  });
});
