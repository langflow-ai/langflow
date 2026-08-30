import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "@/utils/a11y-test";
import DBProviderInputComponent, { DBProviderInput } from "..";

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({
    data: [],
    isFetched: true,
    isFetching: false,
  }),
}));

const baseProps = {
  id: "db-provider-field",
  value: "chroma" as const,
  globalVariables: [],
  disabled: false,
  onValueChange: jest.fn(),
};

const fieldProps = {
  id: "dbprovider_backend",
  value: "chroma" as const,
  disabled: false,
  editNode: false,
  handleOnNewValue: jest.fn(),
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

  it("should_not_emit_a_dead_aria_label_alongside_the_field_label", () => {
    render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput
          {...baseProps}
          ariaLabelledBy="field-label"
          aria-label="Database provider"
        />
      </MemoryRouter>,
    );

    // aria-labelledby already wins; leaving aria-label on the element too
    // would strand a name no assistive tech ever reads.
    expect(
      screen.getByRole("combobox", { name: "Vector store provider" }),
    ).not.toHaveAttribute("aria-label");
  });
});

describe("DBProviderInputComponent", () => {
  // The canvas field label reaches the trigger only if the wrapper forwards
  // ariaLabelledBy out of baseInputProps — testing DBProviderInput alone
  // cannot catch that link being dropped.
  it("should_name_the_trigger_from_the_forwarded_field_label", () => {
    render(
      <MemoryRouter>
        <span id="db-label">Knowledge Base</span>
        <DBProviderInputComponent {...fieldProps} ariaLabelledBy="db-label" />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Knowledge Base" }),
    ).toBeInTheDocument();
  });
});
