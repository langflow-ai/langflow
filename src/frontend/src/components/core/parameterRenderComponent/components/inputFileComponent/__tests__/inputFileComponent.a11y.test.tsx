import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useGetFilesV2 } from "@/controllers/API/queries/file-management";
import { axe } from "@/utils/a11y-test";
import { mockZustandStore } from "../../__tests__/a11y-mock-helpers";
import InputFileComponent from "..";

jest.mock("@/controllers/API/queries/file-management", () => ({
  useGetFilesV2: jest.fn(() => ({ data: undefined })),
}));

jest.mock("@/modals/fileManagerModal", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock(
  "@/modals/fileManagerModal/components/filesRendererComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: (props: { name?: string }) => (
    <svg data-testid={`icon-${props.name}`} />
  ),
  default: (props: { name?: string }) => (
    <svg data-testid={`icon-${props.name}`} />
  ),
}));
jest.mock("@/controllers/API/queries/files/use-post-upload-file", () => ({
  usePostUploadFile: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));
jest.mock("@/shared/hooks/use-file-size-validator", () => ({
  __esModule: true,
  default: () => ({ validateFileSize: jest.fn() }),
}));
jest.mock("../../../../../../stores/alertStore", () =>
  mockZustandStore({ setErrorData: jest.fn() }),
);
jest.mock("../../../../../../stores/flowsManagerStore", () =>
  mockZustandStore({ currentFlowId: "flow-1" }),
);

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

  it("keeps fileManager.selectFiles instead of the field label on the icon-only add-another-file trigger", () => {
    jest.mocked(useGetFilesV2).mockReturnValueOnce({
      data: [{ name: "a.txt", path: "path/a.txt" }],
    } as unknown as ReturnType<typeof useGetFilesV2>);

    render(
      <>
        <span id="field-label">Upload attachment</span>
        <InputFileComponent
          {...baseProps}
          tempFile={false}
          isList
          file_path={["path/a.txt"]}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Select files" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Upload attachment" }),
    ).not.toBeInTheDocument();
  });
});
