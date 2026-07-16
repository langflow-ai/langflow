import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import IOModal from "../playground-modal";

// This suite only asserts the accessible-name fixes on IOModal's own icon
// buttons (the sidebar toggle and the two "Built with Langflow" variants).
// Everything else on the page (chat panel, sidebar session list, output
// panel) is mocked out so the suite doesn't have to model the full
// store/query surface those subtrees depend on.

jest.mock("@/assets/LangflowLogoColor.svg?react", () => ({
  __esModule: true,
  // Forward props (aria-hidden in particular) so the fix is actually testable.
  default: (props: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="langflow-logo-color" {...props} />
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({
    name,
    ...props
  }: { name?: string } & React.HTMLAttributes<HTMLSpanElement>) => (
    <span data-testid={name ? `icon-${name}` : "icon"} {...props} />
  ),
}));

jest.mock(
  "@/components/core/appHeaderComponent/components/ThemeButtons",
  () => ({
    __esModule: true,
    default: () => <div data-testid="theme-buttons" />,
  }),
);

jest.mock("../components/chat-view-wrapper", () => ({
  __esModule: true,
  ChatViewWrapper: () => <div data-testid="chat-view-wrapper" />,
}));

jest.mock("../components/selected-view-field", () => ({
  __esModule: true,
  SelectedViewField: () => <div data-testid="selected-view-field" />,
}));

jest.mock("../components/sidebar-open-view", () => ({
  __esModule: true,
  SidebarOpenView: () => <div data-testid="sidebar-open-view" />,
}));

jest.mock("../../baseModal", () => {
  function MockBaseModal({ children }: { children: React.ReactNode }) {
    return <div data-testid="base-modal">{children}</div>;
  }
  MockBaseModal.Trigger = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  );
  MockBaseModal.Content = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="modal-content">{children}</div>
  );
  return { __esModule: true, default: MockBaseModal };
});

jest.mock("../hooks/useGetFlowId", () => ({
  __esModule: true,
  useGetFlowId: () => "test-flow-id",
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  __esModule: true,
  isAuthenticatedPlayground: () => true,
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  __esModule: true,
  customOpenNewTab: jest.fn(),
}));

jest.mock("@/customization/utils/urls", () => ({
  __esModule: true,
  LangflowButtonRedirectTarget: () => "https://langflow.org",
}));

jest.mock("@/customization/feature-flags", () => ({
  __esModule: true,
  ...jest.requireActual("@/customization/feature-flags"),
  ENABLE_PUBLISH: true,
}));

// Stable object identities: these feed straight into `playground-modal.tsx`
// effect dependency arrays (e.g. the `sessionsFromDb` effect), so a fresh
// object literal on every call would retrigger those effects every render
// and spin into a "Maximum update depth exceeded" loop.
const messagesQueryResult = { isFetched: true, refetch: jest.fn() };
const deleteSessionResult = { mutate: jest.fn() };
const sessionsFromFlowData = { sessions: [] as string[] };
const sessionsFromFlowResult = {
  data: sessionsFromFlowData,
  isLoading: false,
  refetch: jest.fn(),
};

jest.mock("@/controllers/API/queries/messages", () => ({
  __esModule: true,
  useGetMessagesQuery: () => messagesQueryResult,
}));

jest.mock("@/controllers/API/queries/messages/use-delete-sessions", () => ({
  __esModule: true,
  useDeleteSession: () => deleteSessionResult,
}));

jest.mock(
  "@/controllers/API/queries/messages/use-get-sessions-from-flow",
  () => ({
    __esModule: true,
    useGetSessionsFromFlowQuery: () => sessionsFromFlowResult,
  }),
);

const flowState = {
  inputs: [],
  outputs: [],
  nodes: [],
  buildFlow: jest.fn(),
  setIsBuilding: jest.fn(),
  isBuilding: false,
  newChatOnPlayground: false,
  setNewChatOnPlayground: jest.fn(),
  currentFlow: {
    icon: undefined,
    id: "test-flow-id",
    gradient: "1",
    name: "Test Flow",
  },
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof flowState) => unknown) =>
    selector(flowState),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { setIOModalOpen: () => void }) => unknown) =>
    selector({ setIOModalOpen: jest.fn() }),
}));

const alertState = {
  setErrorData: jest.fn(),
  setSuccessData: jest.fn(),
};

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof alertState) => unknown) =>
    selector(alertState),
}));

const messagesState = {
  deleteSession: jest.fn(),
  messages: [],
  removeMessages: jest.fn(),
};

jest.mock("@/stores/messagesStore", () => ({
  __esModule: true,
  useMessagesStore: (selector: (state: typeof messagesState) => unknown) =>
    selector(messagesState),
}));

const utilityState = {
  clientId: "client-1",
  setCurrentSessionId: jest.fn(),
  chatValueStore: "",
  setChatValueStore: jest.fn(),
  eventDelivery: "polling",
  setPlaygroundScrollBehaves: jest.fn(),
};

jest.mock("@/stores/utilityStore", () => ({
  __esModule: true,
  useUtilityStore: (selector: (state: typeof utilityState) => unknown) =>
    selector(utilityState),
}));

const renderPlayground = () =>
  render(
    <TooltipProvider>
      <IOModal
        open
        setOpen={jest.fn()}
        isPlayground
        playgroundPage
        canvasOpen={false}
      >
        <div />
      </IOModal>
    </TooltipProvider>,
  );

describe("IOModal (playground) accessibility", () => {
  it("has no detectable axe violations with the sidebar open", async () => {
    const { container } = renderPlayground();

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("names the sidebar-collapse toggle button", () => {
    renderPlayground();

    expect(
      screen.getByRole("button", { name: "Hide sidebar" }),
    ).toBeInTheDocument();
  });

  it("hides the sidebar-open 'Built with Langflow' logo from assistive tech", () => {
    renderPlayground();

    // Sidebar-open variant: the button has a visible text label, but its
    // decorative logo SVG must still be aria-hidden so AT doesn't announce
    // an unnamed <svg> inside a named button.
    const openVariantLogo = screen.getAllByTestId("langflow-logo-color")[0];
    expect(openVariantLogo).toHaveAttribute("aria-hidden", "true");
  });

  it("flips the toggle's aria-label to 'Show sidebar' once collapsed", () => {
    renderPlayground();

    fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));

    expect(
      screen.queryByRole("button", { name: "Hide sidebar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Show sidebar" }),
    ).toBeInTheDocument();
  });

  it("names the collapsed-sidebar 'Built with Langflow' button and hides its icon", () => {
    renderPlayground();

    fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));

    const collapsedButton = screen.getByRole("button", {
      name: "Built with Langflow",
    });
    expect(collapsedButton).toBeInTheDocument();

    const icon = collapsedButton.querySelector(
      '[data-testid="langflow-logo-color"]',
    );
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("has no detectable axe violations with the sidebar collapsed", async () => {
    const { container } = renderPlayground();

    fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });
});
