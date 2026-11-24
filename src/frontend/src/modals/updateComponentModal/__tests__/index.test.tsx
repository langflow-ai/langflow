import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UpdateComponentModal from "../index";

const mockHandleDuplicate = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/components/common/genericIconComponent", () => () => null);
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => () => null,
);
jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: () => null,
}));
jest.mock("@/pages/MainPage/hooks/use-handle-duplicate", () => () => ({
  handleDuplicate: mockHandleDuplicate,
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlow: null }) => unknown) =>
    selector({ currentFlow: null }),
}));
jest.mock("@/utils/utils", () => ({
  cn: (...classes: Array<string | false>) => classes.filter(Boolean).join(" "),
}));
jest.mock("@/modals/baseModal", () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  );
  const Footer = ({
    submit,
  }: {
    submit: {
      label: string;
      loading: boolean;
      onClick: () => Promise<void>;
    };
  }) => (
    <button
      data-loading={submit.loading}
      data-testid="modal-update-button"
      onClick={() => void submit.onClick()}
    >
      {submit.label}
    </button>
  );
  const BaseModal = ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open: boolean;
  }) => (open ? <div>{children}</div> : null);
  BaseModal.Trigger = Passthrough;
  BaseModal.Header = Passthrough;
  BaseModal.Content = Passthrough;
  BaseModal.Footer = Footer;
  return { __esModule: true, default: BaseModal };
});

const components = [
  {
    id: "node-1",
    display_name: "Prompt",
    icon: "FileText",
    outdated: true,
    blocked: false,
    breakingChange: false,
    userEdited: false,
  },
];

describe("UpdateComponentModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHandleDuplicate.mockResolvedValue(undefined);
  });

  it("stays loading until a full update succeeds, then closes", async () => {
    const user = userEvent.setup();
    const setOpen = jest.fn();
    let resolveUpdate!: () => void;
    const onUpdateNode = jest.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveUpdate = resolve;
        }),
    );

    render(
      <UpdateComponentModal
        open
        setOpen={setOpen}
        onUpdateNode={onUpdateNode}
        components={components}
      />,
    );

    await user.click(screen.getByTestId("modal-update-button"));
    expect(screen.getByTestId("modal-update-button")).toHaveAttribute(
      "data-loading",
      "true",
    );
    expect(setOpen).not.toHaveBeenCalled();

    resolveUpdate();

    await waitFor(() => expect(setOpen).toHaveBeenCalledWith(false));
    expect(screen.getByTestId("modal-update-button")).toHaveAttribute(
      "data-loading",
      "false",
    );
  });

  it("keeps the modal open when any selected update fails", async () => {
    const user = userEvent.setup();
    const setOpen = jest.fn();
    const onUpdateNode = jest.fn().mockRejectedValue(new Error("partial"));

    render(
      <UpdateComponentModal
        open
        setOpen={setOpen}
        onUpdateNode={onUpdateNode}
        components={components}
      />,
    );

    await user.click(screen.getByTestId("modal-update-button"));

    await waitFor(() =>
      expect(screen.getByTestId("modal-update-button")).toHaveAttribute(
        "data-loading",
        "false",
      ),
    );
    expect(onUpdateNode).toHaveBeenCalledTimes(1);
    expect(setOpen).not.toHaveBeenCalled();
  });

  it("reports a backup failure and does not start the update", async () => {
    const user = userEvent.setup();
    const setOpen = jest.fn();
    const onUpdateNode = jest.fn();
    mockHandleDuplicate.mockRejectedValueOnce(new Error("backup failed"));

    render(
      <UpdateComponentModal
        open
        setOpen={setOpen}
        onUpdateNode={onUpdateNode}
        components={components}
      />,
    );

    await user.click(screen.getByTestId("modal-update-button"));

    await waitFor(() =>
      expect(screen.getByTestId("modal-update-button")).toHaveAttribute(
        "data-loading",
        "false",
      ),
    );
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Something went wrong, please try again",
    });
    expect(onUpdateNode).not.toHaveBeenCalled();
    expect(setOpen).not.toHaveBeenCalled();
  });
});
