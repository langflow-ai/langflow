import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import EditShortcutButton from "../EditShortcutButton";

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetShortcuts = jest.fn();
const mockUpdateUniqueShortcut = jest.fn();

type AlertStoreState = {
  setSuccessData: typeof mockSetSuccessData;
  setErrorData: typeof mockSetErrorData;
};

type ShortcutsStoreState = {
  setShortcuts: typeof mockSetShortcuts;
  updateUniqueShortcut: typeof mockUpdateUniqueShortcut;
};

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: AlertStoreState) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("@/stores/shortcuts", () => ({
  __esModule: true,
  useShortcutsStore: (selector: (state: ShortcutsStoreState) => unknown) =>
    selector({
      setShortcuts: mockSetShortcuts,
      updateUniqueShortcut: mockUpdateUniqueShortcut,
    }),
}));

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
};

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: ButtonProps) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock(
  "@/components/common/renderIconComponent/components/renderKey",
  () => ({
    __esModule: true,
    default: ({ value }: { value: string }) => <span>{value}</span>,
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/modals/baseModal", () => {
  interface ChildrenProps {
    children: ReactNode;
  }

  interface HeaderProps extends ChildrenProps {
    description?: string;
  }

  interface TriggerProps extends ChildrenProps {
    disable?: boolean;
    asChild?: boolean;
  }

  interface BaseModalProps extends ChildrenProps {
    open?: boolean;
    setOpen?: (open: boolean) => void;
    size?: string;
  }

  const MockContent = ({ children }: ChildrenProps) => (
    <div data-testid="modal-content">{children}</div>
  );
  const MockHeader = ({ children, description }: HeaderProps) => (
    <div data-testid="modal-header" data-description={description}>
      {children}
    </div>
  );
  const MockTrigger = ({ children, disable }: TriggerProps) => (
    <div data-testid="modal-trigger" data-disabled={disable}>
      {children}
    </div>
  );
  const MockFooter = ({ children }: ChildrenProps) => (
    <div data-testid="modal-footer">{children}</div>
  );

  function MockBaseModal({ children, open, size }: BaseModalProps) {
    if (!open) {
      return <div data-testid="base-modal-closed" data-size={size} />;
    }

    return (
      <div data-testid="base-modal" data-size={size}>
        {children}
      </div>
    );
  }

  MockContent.displayName = "Content";
  MockHeader.displayName = "Header";
  MockTrigger.displayName = "Trigger";
  MockFooter.displayName = "Footer";

  MockBaseModal.Content = MockContent;
  MockBaseModal.Header = MockHeader;
  MockBaseModal.Trigger = MockTrigger;
  MockBaseModal.Footer = MockFooter;

  return { __esModule: true, default: MockBaseModal };
});

describe("EditShortcutButton", () => {
  let setItemSpy: jest.SpyInstance<void, [string, string]>;

  beforeEach(() => {
    jest.clearAllMocks();
    setItemSpy = jest
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    setItemSpy.mockRestore();
  });

  it("resets shortcut to default value", async () => {
    const user = userEvent.setup();
    const shortcuts = [
      { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
      { name: "Code", display_name: "Code", shortcut: "mod+." },
    ];
    const defaultShortcuts = [
      { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
      { name: "Code", display_name: "Code", shortcut: "space" },
    ];

    const setOpen = jest.fn();
    const setSelected = jest.fn();

    render(
      <EditShortcutButton
        open={true}
        setOpen={setOpen}
        shortcut={["Code"]}
        shortcuts={shortcuts}
        defaultShortcuts={defaultShortcuts}
        setSelected={setSelected}
      >
        <div />
      </EditShortcutButton>,
    );

    await user.click(screen.getByRole("button", { name: "Reset" }));

    expect(mockSetShortcuts).toHaveBeenCalledWith([
      { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
      { name: "Code", display_name: "Code", shortcut: "space" },
    ]);
    expect(mockUpdateUniqueShortcut).toHaveBeenCalledWith("code", "space");
    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "Code shortcut reset to default",
    });
    expect(localStorage.setItem).toHaveBeenCalledWith(
      "langflow-shortcuts",
      JSON.stringify([
        { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
        { name: "Code", display_name: "Code", shortcut: "space" },
      ]),
    );
  });
});
