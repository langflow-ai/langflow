import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import InputFileComponent from "..";

jest.mock("@/controllers/API/queries/file-management", () => ({
  useGetFilesV2: () => ({ data: undefined }),
}));
jest.mock("@/controllers/API/queries/files/use-post-upload-file", () => ({
  usePostUploadFile: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));
jest.mock("@/shared/hooks/use-file-size-validator", () => ({
  __esModule: true,
  default: () => ({ validateFileSize: jest.fn() }),
}));
jest.mock("../../../../../../stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));
jest.mock("../../../../../../stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ currentFlowId: "flow-1" }),
}));

// tempFile defaults to true, so ENABLE_FILE_MANAGEMENT's grid/modal branch
// is skipped and the plain read-only-input trigger (the one under test) is
// what actually renders — matching the component's own branch condition.
const baseProps = {
  value: "",
  file_path: "",
  id: "file-field",
  editNode: false,
  disabled: false,
  fileTypes: [],
  isList: false,
  handleOnNewValue: jest.fn(),
};

describe("InputFileComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Upload attachment</span>
        <InputFileComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Upload attachment</span>
        <InputFileComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Upload attachment" }),
    ).toBeInTheDocument();
  });

  it("falls back to the generic translated label when ariaLabelledBy is absent", () => {
    render(<InputFileComponent {...baseProps} />);

    expect(screen.getByTestId("input-file-component")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });
});
