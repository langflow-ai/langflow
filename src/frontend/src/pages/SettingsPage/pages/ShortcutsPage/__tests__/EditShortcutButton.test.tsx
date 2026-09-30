import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useEffect, useState } from "react";
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
    onOpenAutoFocus?: (e: Event) => void;
    onCloseAutoFocus?: (e: Event) => void;
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

  function MockBaseModal({
    children,
    open,
    size,
    onOpenAutoFocus,
    onCloseAutoFocus,
  }: BaseModalProps) {
    // Real Radix Dialog fires onOpenAutoFocus once, on mount, when open —
    // simulate that here so tests can verify the actual focus target
    // instead of just asserting a tabIndex attribute exists.
    useEffect(() => {
      if (open && onOpenAutoFocus) {
        onOpenAutoFocus({ preventDefault: () => {} } as Event);
      }
    }, [open, onOpenAutoFocus]);

    // Real Radix Dialog fires onCloseAutoFocus from its own unmount
    // cleanup, regardless of *why* it unmounts — including a parent that
    // conditionally renders the modal (e.g. `{open && <Modal />}`) and
    // tears the whole subtree down as soon as it closes.
    useEffect(() => {
      return () => {
        onCloseAutoFocus?.({ preventDefault: () => {} } as Event);
      };
    }, [onCloseAutoFocus]);

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

  describe("accessibility", () => {
    const shortcuts = [
      { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
      { name: "Code", display_name: "Code", shortcut: "mod+." },
    ];
    const defaultShortcuts = [
      { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
      { name: "Code", display_name: "Code", shortcut: "space" },
    ];

    function renderModal() {
      return render(
        <EditShortcutButton
          open={true}
          setOpen={jest.fn()}
          shortcut={["Code"]}
          shortcuts={shortcuts}
          defaultShortcuts={defaultShortcuts}
          setSelected={jest.fn()}
        >
          <div />
        </EditShortcutButton>,
      );
    }

    it("has no detectable axe violations while open", async () => {
      const { container } = renderModal();

      const results = await axe(container);

      expect(results).toHaveNoViolations();
    });

    it("exposes the recorded key combination in a live region for screen readers", () => {
      renderModal();

      const status = screen.getByRole("status");

      expect(status).toHaveAttribute("aria-live", "polite");
      expect(status).toHaveTextContent("."); // shortcutInitialValue "mod+." renders the "." key
    });

    it("updates the accessible live region as new keys are recorded", async () => {
      renderModal();

      const status = screen.getByRole("status");
      expect(status).toHaveTextContent(".");

      fireEvent.keyDown(document, { key: "a" });

      expect(status).toHaveTextContent("A");
    });

    it("is reachable via Tab", () => {
      renderModal();

      const status = screen.getByRole("status");

      expect(status).toHaveAttribute("tabIndex", "0");
    });

    // Regression guard: the modal previously left focus on the dialog
    // container on open (BaseModal's default, to avoid popping the close
    // button's tooltip) — a WCAG 2.4.3 gap for a modal whose entire purpose
    // is capturing a keyboard combination. recordingRef existed but was
    // never attached or focused; onOpenAutoFocus was never wired up.
    it("receives focus automatically when opened, not the dialog container", () => {
      renderModal();

      const status = screen.getByRole("status");

      expect(status).toHaveFocus();
    });

    // Regression guard: closing the modal (Esc, etc.) previously dropped
    // focus to <body> instead of returning it to the row/cell that opened
    // it. This happened because the parent that owns `open` state (e.g.
    // ShortcutsPage) conditionally mounts this whole component with
    // `{open && <EditShortcutButton ... />}`, tearing down the dialog's
    // own focus-restore bookkeeping before it could hand focus back.
    it("returns focus to the element that opened the modal when it closes, not <body>", () => {
      function Wrapper() {
        const [open, setOpen] = useState(false);
        return (
          <>
            <button
              type="button"
              data-testid="trigger-cell"
              onClick={() => setOpen(true)}
            >
              Docs
            </button>
            {open && (
              <EditShortcutButton
                open={open}
                setOpen={setOpen}
                shortcut={["Code"]}
                shortcuts={shortcuts}
                defaultShortcuts={defaultShortcuts}
                setSelected={jest.fn()}
              >
                <div />
              </EditShortcutButton>
            )}
          </>
        );
      }

      render(<Wrapper />);
      const trigger = screen.getByTestId("trigger-cell");
      trigger.focus();
      expect(trigger).toHaveFocus();

      fireEvent.click(trigger);
      expect(screen.getByRole("status")).toHaveFocus();

      // Applying/resetting (like Esc in the real Dialog) calls setOpen(false),
      // which unmounts the whole `{open && <EditShortcutButton />}` subtree in
      // ShortcutsPage — the same teardown that used to drop focus to <body>.
      fireEvent.click(screen.getByRole("button", { name: "Reset" }));

      expect(screen.queryByRole("status")).not.toBeInTheDocument();
      expect(document.body).not.toHaveFocus();
      expect(trigger).toHaveFocus();
    });

    it("exposes Apply and Reset actions as named, focusable buttons", () => {
      renderModal();

      const applyButton = screen.getByRole("button", { name: "Apply" });
      const resetButton = screen.getByRole("button", { name: "Reset" });

      expect(applyButton).toBeInTheDocument();
      expect(resetButton).toBeInTheDocument();
      applyButton.focus();
      expect(applyButton).toHaveFocus();
    });

    it("ignores recorded keydowns once the modal is closed (no violations on closed state)", async () => {
      const { container } = render(
        <EditShortcutButton
          open={false}
          setOpen={jest.fn()}
          shortcut={["Code"]}
          shortcuts={shortcuts}
          defaultShortcuts={defaultShortcuts}
          setSelected={jest.fn()}
        >
          <div />
        </EditShortcutButton>,
      );

      const results = await axe(container);

      expect(results).toHaveNoViolations();
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });
  });
});
