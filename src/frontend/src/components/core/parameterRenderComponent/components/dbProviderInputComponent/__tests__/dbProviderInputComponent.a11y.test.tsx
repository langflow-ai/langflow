import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "@/utils/a11y-test";
import { DBProviderInput } from "..";

const baseProps = {
  id: "db-provider-field",
  value: "chroma" as const,
  globalVariables: [],
  disabled: false,
  onValueChange: jest.fn(),
};

describe("DBProviderInput", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput {...baseProps} ariaLabelledBy="field-label" />
      </MemoryRouter>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: aria-labelledby (field label) must win over the
  // literal aria-label prop, and must not be composed with the selected
  // provider's name (role="combobox" screen-reader double-announce lesson
  // from dropdownComponent/modelInputComponent/connectionComponent).
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput
          {...baseProps}
          ariaLabelledBy="field-label"
          aria-label="Should be overridden"
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Vector store provider" }),
    ).toBeInTheDocument();
  });

  it("falls back to the literal aria-label when ariaLabelledBy is absent", () => {
    render(
      <MemoryRouter>
        <DBProviderInput {...baseProps} aria-label="Database provider" />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Database provider" }),
    ).toBeInTheDocument();
  });
});
