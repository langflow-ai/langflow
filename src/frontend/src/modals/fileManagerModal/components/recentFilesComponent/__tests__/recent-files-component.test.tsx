import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import type { FileType } from "@/types/file_management";
import { setRelativePathForServerPath } from "@/utils/file-relative-path-map";
import RecentFilesComponent from "../index";

type InputProps = ComponentPropsWithoutRef<"input">;
type ButtonProps = ComponentPropsWithoutRef<"button"> & {
  children?: ReactNode;
};
type CheckboxProps = Omit<
  ComponentPropsWithoutRef<"input">,
  "type" | "checked" | "onChange"
> & {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
};

type AlertStoreState = {
  setErrorData: (args: unknown) => void;
  setSuccessData: (args: unknown) => void;
};

jest.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, ...props }: InputProps) => (
    <input value={value} onChange={onChange} {...props} />
  ),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: AlertStoreState) => unknown) =>
    selector({
      setErrorData: jest.fn(),
      setSuccessData: jest.fn(),
    }),
}));

jest.mock("@/controllers/API/queries/file-management/use-delete-files", () => ({
  useDeleteFilesV2: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
}));

jest.mock(
  "@/controllers/API/queries/file-management/use-put-rename-file",
  () => ({
    usePostRenameFileV2: () => ({
      mutate: jest.fn(),
    }),
  }),
);

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: ButtonProps) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({ checked, onCheckedChange, ...props }: CheckboxProps) => (
    <input
      type="checkbox"
      aria-checked={checked}
      onChange={() => onCheckedChange?.(!checked)}
      {...props}
    />
  ),
}));

jest.mock("../../filesRendererComponent", () => ({
  __esModule: true,
  default: ({ files }: { files: FileType[] }) => (
    <div data-testid="files-renderer">{files.map((f) => f.path).join("|")}</div>
  ),
}));

jest.mock(
  "../../filesRendererComponent/components/fileRendererComponent",
  () => ({
    __esModule: true,
    default: ({ file }: { file: FileType }) => (
      <div data-testid={`file-row-${file.path}`}>{file.path}</div>
    ),
  }),
);

function makeServerFile(overrides: Partial<FileType>): FileType {
  return {
    id: overrides.id ?? "id",
    user_id: overrides.user_id ?? "user",
    provider: overrides.provider ?? "local",
    name: overrides.name ?? "file",
    path: overrides.path ?? "/server/file.txt",
    created_at: overrides.created_at ?? "2020-01-01",
    size: overrides.size ?? 1,
    updated_at: overrides.updated_at,
    progress: overrides.progress,
    file: overrides.file,
    type: overrides.type,
    disabled: overrides.disabled,
  };
}

describe("RecentFilesComponent", () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.clearAllMocks();
  });

  it("renders hierarchical folder tree when relative paths exist and search is empty", () => {
    const a = makeServerFile({ id: "a", name: "a", path: "/server/a.txt" });
    const b = makeServerFile({ id: "b", name: "b", path: "/server/b.txt" });

    setRelativePathForServerPath(a.path, "Root/a.txt");
    setRelativePathForServerPath(b.path, "Root/Sub/b.txt");

    render(
      <RecentFilesComponent
        files={[a, b]}
        selectedFiles={[]}
        setSelectedFiles={jest.fn()}
        types={["txt"]}
        isList={true}
      />,
    );

    expect(screen.getByText("Root")).toBeInTheDocument();
    expect(screen.getByTestId("file-row-/server/a.txt")).toBeInTheDocument();
    expect(screen.getByTestId("file-row-/server/b.txt")).toBeInTheDocument();
    expect(screen.queryByTestId("files-renderer")).not.toBeInTheDocument();
  });

  it("switches to flat renderer when searching", () => {
    const a = makeServerFile({ id: "a", name: "alpha", path: "/server/a.txt" });
    setRelativePathForServerPath(a.path, "Root/a.txt");

    render(
      <RecentFilesComponent
        files={[a]}
        selectedFiles={[]}
        setSelectedFiles={jest.fn()}
        types={["txt"]}
        isList={true}
      />,
    );

    fireEvent.change(screen.getByTestId("search-files-input"), {
      target: { value: "alp" },
    });

    expect(screen.getByTestId("files-renderer")).toBeInTheDocument();
  });
});
