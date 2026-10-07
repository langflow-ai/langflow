import { render, screen } from "@testing-library/react";
import CustomInputFileComponent from "../custom-input-file";

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputFileComponent",
  () =>
    function MockInputFileComponent(props: { ariaLabelledBy?: string }) {
      return (
        <div
          data-testid="mock-input-file"
          data-aria-labelledby={props.ariaLabelledBy}
        />
      );
    },
);

const baseProps = {
  value: "",
  file_path: "",
  id: "file-field",
  editNode: false,
  disabled: false,
  fileTypes: [],
  handleOnNewValue: jest.fn(),
};

describe("CustomInputFileComponent", () => {
  // Regression guard: this wrapper explicitly lists the props it forwards
  // to InputFileComponent (rather than spreading), so a newly added prop
  // like ariaLabelledBy can silently be dropped on the floor — as happened
  // with custom-linkComponent.tsx earlier in this remediation.
  it("forwards ariaLabelledBy through to InputFileComponent", () => {
    render(
      <CustomInputFileComponent {...baseProps} ariaLabelledBy="field-label" />,
    );

    expect(screen.getByTestId("mock-input-file")).toHaveAttribute(
      "data-aria-labelledby",
      "field-label",
    );
  });

  // Fallback case: forwarding must not choke or fabricate a value when no
  // field label is wired up — it should just pass undefined through.
  it("forwards an absent ariaLabelledBy through as undefined", () => {
    render(<CustomInputFileComponent {...baseProps} />);

    expect(screen.getByTestId("mock-input-file")).not.toHaveAttribute(
      "data-aria-labelledby",
    );
  });
});
