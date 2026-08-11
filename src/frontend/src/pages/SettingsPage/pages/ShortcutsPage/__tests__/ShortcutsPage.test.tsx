import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColDef } from "ag-grid-community";
import { axe } from "jest-axe";
import ShortcutsPage from "..";

const mockSetShortcuts = jest.fn();
const mockUpdateUniqueShortcut = jest.fn();

const shortcuts = [
  { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
  { name: "Code", display_name: "Code", shortcut: "mod+." },
];

jest.mock("@/stores/shortcuts", () => ({
  __esModule: true,
  useShortcutsStore: (selector: (state: unknown) => unknown) =>
    selector({
      shortcuts,
      setShortcuts: mockSetShortcuts,
      updateUniqueShortcut: mockUpdateUniqueShortcut,
    }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true">
      {name}
    </span>
  ),
}));

type CapturedTableProps = {
  onCellDoubleClicked: (event: { data: { name: string } }) => void;
  onCellKeyDown: (event: {
    data: { name: string };
    event: KeyboardEvent;
  }) => void;
  columnDefs: ColDef[];
  rowData: Array<{ name: string; display_name: string; shortcut: string }>;
};

let capturedTableProps: CapturedTableProps | null = null;

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: (props: CapturedTableProps) => {
      capturedTableProps = props;
      return (
        <table aria-label="Shortcuts">
          <tbody>
            {props.rowData.map((row) => (
              <tr
                key={row.name}
                tabIndex={0}
                data-testid={`row-${row.name}`}
                onDoubleClick={() => props.onCellDoubleClicked({ data: row })}
                onKeyDown={(e) =>
                  props.onCellKeyDown({
                    data: row,
                    event: e.nativeEvent,
                  })
                }
              >
                <td>{row.display_name}</td>
                <td>{row.shortcut}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    },
  }),
);

let capturedEditShortcutProps: Record<string, unknown> | null = null;

jest.mock("../EditShortcutButton", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    capturedEditShortcutProps = props;
    return <div data-testid="edit-shortcut-modal" />;
  },
}));

describe("ShortcutsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedTableProps = null;
    capturedEditShortcutProps = null;
    localStorage.clear();
  });

  it("has no detectable axe violations", async () => {
    const { container } = render(<ShortcutsPage />);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("exposes the page title as an accessible heading", () => {
    render(<ShortcutsPage />);

    expect(
      screen.getByRole("heading", { name: /shortcuts/i }),
    ).toBeInTheDocument();
  });

  it("exposes the restore action as a named, focusable button", () => {
    render(<ShortcutsPage />);

    const restoreButton = screen.getByRole("button", {
      name: /restore/i,
    });

    expect(restoreButton).toBeInTheDocument();
    restoreButton.focus();
    expect(restoreButton).toHaveFocus();
  });

  it("opens the shortcut editor via keyboard (Enter) without requiring a pointer", async () => {
    const user = userEvent.setup();
    render(<ShortcutsPage />);

    const row = screen.getByTestId("row-Docs");
    row.focus();
    await user.keyboard("{Enter}");

    expect(capturedEditShortcutProps).not.toBeNull();
    expect(capturedEditShortcutProps?.disable).toBe(false);
    expect(capturedEditShortcutProps?.shortcut).toEqual(["Docs"]);
  });

  it("opens the shortcut editor via keyboard (Space) without requiring a pointer", async () => {
    const user = userEvent.setup();
    render(<ShortcutsPage />);

    const row = screen.getByTestId("row-Code");
    row.focus();
    await user.keyboard(" ");

    expect(capturedEditShortcutProps).not.toBeNull();
    expect(capturedEditShortcutProps?.shortcut).toEqual(["Code"]);
  });

  it("ignores non-activation keys so the editor does not open unexpectedly", () => {
    render(<ShortcutsPage />);

    capturedTableProps?.onCellKeyDown({
      data: { name: "Docs" },
      event: new KeyboardEvent("keydown", { key: "a" }),
    });

    expect(capturedEditShortcutProps).toBeNull();
  });

  it("restores default shortcuts and announces it via a named button without a pointer", async () => {
    const user = userEvent.setup();
    render(<ShortcutsPage />);

    await user.click(screen.getByRole("button", { name: /restore/i }));

    expect(mockSetShortcuts).toHaveBeenCalled();
    expect(localStorage.getItem("langflow-shortcuts")).toBeNull();
  });
});
