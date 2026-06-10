/**
 * Component tests for the FlowBuilderWelcome overlay.
 *
 * Treats the overlay as a presentational component driven by injected
 * callbacks — the actual wire-up to the store / templates modal / assistant
 * panel lives in the parent, so these tests can assert behavior in isolation.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FlowBuilderWelcome } from "../flow-builder-welcome";

const WELCOME_TITLE = "What do you want to build?";
const WELCOME_TEXTAREA_PLACEHOLDER = "Describe your flow...";
const WELCOME_SIMPLE_AGENT_LABEL = "Simple Agent";
const WELCOME_VECTOR_STORE_RAG_LABEL = "Vector Store RAG";
const WELCOME_BROWSE_MORE_LABEL = "Browse more...";

// Mock the icon component to keep these tests free from SVG / asset noise.
jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} />;
  };
});

// ShadTooltip wraps Radix Tooltip which needs a TooltipProvider ancestor —
// the welcome renders standalone in these tests. Pass children through.
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => children,
}));

// ModelSelector pulls in React Query (useGetModelProviders) which needs a
// QueryClientProvider wrapper. These tests focus on the welcome's own
// callbacks/wiring, so replace the selector with a stub.
jest.mock("@/components/core/assistantPanel/components/model-selector", () => ({
  ModelSelector: () => <div data-testid="mock-model-selector" />,
}));

// The shared model state hook touches ``localStorage`` on init — keep that
// path inert and predictable in tests.
jest.mock(
  "@/components/core/assistantPanel/hooks/use-assistant-selected-model",
  () => ({
    useAssistantSelectedModel: () => [null, jest.fn()],
  }),
);

// useEnabledModels hits React Query. Default the stub to "has providers" so
// the normal input renders; individual tests can override via the mockable
// reference below.
const mockUseEnabledModels = jest.fn(() => ({
  hasEnabledModels: true,
  filteredProviders: [],
  isLoading: false,
}));
jest.mock("@/components/core/assistantPanel/hooks/use-enabled-models", () => ({
  useEnabledModels: () => mockUseEnabledModels(),
}));

// ModelProviderModal is a heavy settings surface — stub it; we only assert
// it mounts when the configure CTA is clicked.
jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="mock-model-provider-modal" /> : null,
}));

function makeProps(
  overrides: Partial<Parameters<typeof FlowBuilderWelcome>[0]> = {},
) {
  return {
    onSubmit: jest.fn(),
    onSelectTemplate: jest.fn(),
    onBrowseMore: jest.fn(),
    onClose: jest.fn(),
    onSelectRailItem: jest.fn(),
    ...overrides,
  };
}

describe("FlowBuilderWelcome", () => {
  beforeEach(() => {
    mockUseEnabledModels.mockReturnValue({
      hasEnabledModels: true,
      filteredProviders: [],
      isLoading: false,
    });
  });

  describe("no model provider configured", () => {
    it("should_show_configure_provider_state_instead_of_textarea", () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: false,
      });
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(
        screen.getByTestId("flow-builder-welcome-no-provider"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("flow-builder-welcome-textarea"),
      ).not.toBeInTheDocument();
    });

    it("should_keep_template_buttons_available_with_no_provider", () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: false,
      });
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(
        screen.getByTestId("flow-builder-welcome-template-simple-agent"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("flow-builder-welcome-browse-more"),
      ).toBeInTheDocument();
    });

    it("should_open_provider_modal_when_configure_clicked", async () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: false,
      });
      render(<FlowBuilderWelcome {...makeProps()} />);
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-configure-providers"),
      );
      expect(
        screen.getByTestId("mock-model-provider-modal"),
      ).toBeInTheDocument();
    });

    it("should_NOT_show_configure_state_while_models_are_loading", () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: true,
      });
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(
        screen.queryByTestId("flow-builder-welcome-no-provider"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("flow-builder-welcome-textarea"),
      ).toBeInTheDocument();
    });
  });

  describe("rendering", () => {
    it("should_render_the_headline_and_textarea_placeholder", () => {
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(screen.getByText(WELCOME_TITLE)).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText(WELCOME_TEXTAREA_PLACEHOLDER),
      ).toBeInTheDocument();
    });

    it("should_render_both_quick_template_buttons", () => {
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(
        screen.getByRole("button", { name: WELCOME_SIMPLE_AGENT_LABEL }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: WELCOME_VECTOR_STORE_RAG_LABEL }),
      ).toBeInTheDocument();
    });

    it("should_render_the_browse_more_templates_link", () => {
      render(<FlowBuilderWelcome {...makeProps()} />);
      expect(
        screen.getByRole("button", { name: WELCOME_BROWSE_MORE_LABEL }),
      ).toBeInTheDocument();
    });
  });

  describe("submit", () => {
    it("should_call_onSubmit_with_trimmed_text_when_user_clicks_send", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      await userEvent.type(
        screen.getByPlaceholderText(WELCOME_TEXTAREA_PLACEHOLDER),
        "  build a chatbot  ",
      );
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-send-button"),
      );

      expect(props.onSubmit).toHaveBeenCalledWith("build a chatbot");
    });

    it("should_NOT_call_onSubmit_when_textarea_is_empty_or_only_whitespace", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      await userEvent.type(
        screen.getByPlaceholderText(WELCOME_TEXTAREA_PLACEHOLDER),
        "   ",
      );
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-send-button"),
      );

      expect(props.onSubmit).not.toHaveBeenCalled();
    });

    it("should_call_onSubmit_when_user_presses_Enter_without_shift", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const textarea = screen.getByPlaceholderText(
        WELCOME_TEXTAREA_PLACEHOLDER,
      );
      await userEvent.type(textarea, "hello{Enter}");

      expect(props.onSubmit).toHaveBeenCalledWith("hello");
    });

    it("should_NOT_call_onSubmit_when_user_presses_Shift_Enter", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const textarea = screen.getByPlaceholderText(
        WELCOME_TEXTAREA_PLACEHOLDER,
      );
      await userEvent.type(textarea, "line1{Shift>}{Enter}{/Shift}line2");

      expect(props.onSubmit).not.toHaveBeenCalled();
      expect(textarea).toHaveValue("line1\nline2");
    });
  });

  describe("quick templates", () => {
    it("should_call_onSelectTemplate_with_simple_agent_name_key_when_button_is_clicked", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByRole("button", { name: WELCOME_SIMPLE_AGENT_LABEL }),
      );
      expect(props.onSelectTemplate).toHaveBeenCalledWith("simple_agent");
    });

    it("should_call_onSelectTemplate_with_vector_store_rag_name_key_when_button_is_clicked", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByRole("button", { name: WELCOME_VECTOR_STORE_RAG_LABEL }),
      );
      expect(props.onSelectTemplate).toHaveBeenCalledWith("vector_store_rag");
    });
  });

  describe("browse more", () => {
    it("should_call_onBrowseMore_when_the_browse_link_is_clicked", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByRole("button", { name: WELCOME_BROWSE_MORE_LABEL }),
      );
      expect(props.onBrowseMore).toHaveBeenCalledTimes(1);
    });
  });

  describe("faux sidebar rail", () => {
    it("should_call_onSelectRailItem_with_section_id_when_rail_icon_is_clicked", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-faux-rail-components"),
      );
      expect(props.onSelectRailItem).toHaveBeenCalledWith("components");
    });

    it("should_NOT_call_onClose_when_a_rail_icon_is_clicked", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-faux-rail-memories"),
      );
      expect(props.onClose).not.toHaveBeenCalled();
    });
  });

  describe("close paths", () => {
    it("should_call_onClose_when_user_clicks_the_backdrop", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-backdrop"),
      );
      expect(props.onClose).toHaveBeenCalledTimes(1);
    });

    it("should_NOT_call_onClose_when_user_clicks_inside_the_content_panel", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByPlaceholderText(WELCOME_TEXTAREA_PLACEHOLDER),
      );
      expect(props.onClose).not.toHaveBeenCalled();
    });

    it("should_call_onClose_when_user_presses_Escape", async () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      await userEvent.keyboard("{Escape}");
      expect(props.onClose).toHaveBeenCalledTimes(1);
    });
  });
});
