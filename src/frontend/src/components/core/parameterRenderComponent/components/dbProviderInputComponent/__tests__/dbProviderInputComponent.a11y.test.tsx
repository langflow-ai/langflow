import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import DBProviderInputComponent, { DBProviderInput } from "..";

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({
    data: [],
    isFetched: true,
    isFetching: false,
  }),
}));

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
}));

const fieldProps = {
  id: "dbprovider_backend",
  value: "chroma" as const,
  disabled: false,
  editNode: false,
  handleOnNewValue: jest.fn(),
};

describe("DBProviderInputComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="db-label">Knowledge Base</span>
        <DBProviderInputComponent {...fieldProps} ariaLabelledBy="db-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_name_the_trigger_from_the_forwarded_field_label", () => {
    render(
      <>
        <span id="db-label">Knowledge Base</span>
        <DBProviderInputComponent {...fieldProps} ariaLabelledBy="db-label" />
      </>,
    );
    expect(
      screen.getByRole("combobox", { name: "Knowledge Base" }),
    ).toBeInTheDocument();
  });

  it("should_keep_the_aria_label_when_no_field_label_is_forwarded", () => {
    // Modal callers (createMemoryModal, knowledgeBaseUploadModal) pass
    // aria-label directly and have no canvas field label to reference.
    render(
      <DBProviderInput
        id="kb-db-provider"
        value="chroma"
        globalVariables={[]}
        aria-label="Database provider"
        onValueChange={jest.fn()}
      />,
    );
    expect(
      screen.getByRole("combobox", { name: "Database provider" }),
    ).toBeInTheDocument();
  });

  it("should_not_emit_a_dead_aria_label_alongside_the_field_label", () => {
    render(
      <>
        <span id="db-label">Knowledge Base</span>
        <DBProviderInput
          id="kb-db-provider"
          value="chroma"
          globalVariables={[]}
          aria-label="Database provider"
          ariaLabelledBy="db-label"
          onValueChange={jest.fn()}
        />
      </>,
    );
    // aria-labelledby already wins; leaving aria-label on the element too
    // would strand a name no assistive tech ever reads.
    const trigger = screen.getByRole("combobox", { name: "Knowledge Base" });
    expect(trigger).not.toHaveAttribute("aria-label");
  });
});
