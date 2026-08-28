/**
 * Component tests for the FlowBuilderWelcome overlay.
 *
 * Treats the overlay as a presentational component driven by injected
 * callbacks — the actual wire-up to the store / templates modal / assistant
 * panel lives in the parent, so these tests can assert behavior in isolation.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AssistantModel } from "@/components/core/assistantPanel/assistant-panel.types";
import { DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH } from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
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

const SELECTED_MODEL: AssistantModel = {
  id: "OpenAI-gpt-4o",
  name: "gpt-4o",
  provider: "OpenAI",
  displayName: "gpt-4o",
};
let mockSelectedModel: AssistantModel | null = SELECTED_MODEL;

// The shared model state hook touches ``localStorage`` on init — keep that
// path predictable in tests while still exercising authorization of the
// selected value.
jest.mock(
  "@/components/core/assistantPanel/hooks/use-assistant-selected-model",
  () => ({
    useAssistantSelectedModel: () => [mockSelectedModel, jest.fn()],
  }),
);

// useEnabledModels hits React Query. Default the stub to "has providers" so
// the normal input renders; individual tests can override via the mockable
// reference below.
const mockUseEnabledModels = jest.fn(() => ({
  hasEnabledModels: true,
  filteredProviders: [],
  isLoading: false,
  isError: false,
  isCatalogReady: true,
  isModelEnabled: (model: AssistantModel | null): boolean => model !== null,
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

const example = (name_key: string) =>
  ({ id: name_key, name: name_key, name_key }) as never;

/** Both quick templates plus one other, i.e. an unrestricted catalog. */
const FULL_CATALOG = [
  example("simple_agent"),
  example("vector_store_rag"),
  example("basic_prompting"),
];

describe("FlowBuilderWelcome", () => {
  beforeEach(() => {
    useFlowsManagerStore.setState({ examples: FULL_CATALOG });
    mockSelectedModel = SELECTED_MODEL;
    mockUseEnabledModels.mockReturnValue({
      hasEnabledModels: true,
      filteredProviders: [],
      isLoading: false,
      isError: false,
      isCatalogReady: true,
      isModelEnabled: (model: AssistantModel | null): boolean => model !== null,
    });
    useUtilityStore
      .getState()
      .setAssistantMaxMessageLength(DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH);
  });

  describe("no model provider configured", () => {
    it("should_show_configure_provider_state_instead_of_textarea", () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: false,
        isError: false,
        isCatalogReady: true,
        isModelEnabled: () => false,
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
        isError: false,
        isCatalogReady: true,
        isModelEnabled: () => false,
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
        isError: false,
        isCatalogReady: true,
        isModelEnabled: () => false,
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
        isError: false,
        isCatalogReady: false,
        isModelEnabled: () => false,
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

    it("should_disable_send_and_block_Enter_while_the_scoped_catalog_is_loading", async () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: false,
        filteredProviders: [],
        isLoading: true,
        isError: false,
        isCatalogReady: false,
        isModelEnabled: () => false,
      });
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const textarea = screen.getByPlaceholderText(
        WELCOME_TEXTAREA_PLACEHOLDER,
      );
      await userEvent.type(textarea, "build a scoped agent");

      expect(
        screen.getByTestId("flow-builder-welcome-send-button"),
      ).toBeDisabled();
      fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
      expect(props.onSubmit).not.toHaveBeenCalled();
    });

    it("should_reject_a_stale_saved_model_after_the_flow_scope_changes", async () => {
      mockUseEnabledModels.mockReturnValue({
        hasEnabledModels: true,
        filteredProviders: [],
        isLoading: false,
        isError: false,
        isCatalogReady: true,
        isModelEnabled: () => false,
      });
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const textarea = screen.getByPlaceholderText(
        WELCOME_TEXTAREA_PLACEHOLDER,
      );
      await userEvent.type(textarea, "build a scoped agent");

      expect(
        screen.getByTestId("flow-builder-welcome-send-button"),
      ).toBeDisabled();
      fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
      expect(props.onSubmit).not.toHaveBeenCalled();
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

  describe("catalog policy", () => {
    it("should_hide_a_quick_template_its_catalog_no_longer_offers", () => {
      // Clicking a button for a blocked template only fails the lookup, so it
      // is not offered at all.
      useFlowsManagerStore.setState({
        examples: [example("vector_store_rag")],
      });

      render(<FlowBuilderWelcome {...makeProps()} />);

      expect(
        screen.queryByTestId("flow-builder-welcome-template-simple-agent"),
      ).toBeNull();
      expect(
        screen.getByTestId("flow-builder-welcome-template-vector-store-rag"),
      ).toBeInTheDocument();
    });

    it("should_keep_browse_more_while_any_template_survives", () => {
      // The modal is worth opening for templates that have no button here.
      useFlowsManagerStore.setState({ examples: [example("basic_prompting")] });

      render(<FlowBuilderWelcome {...makeProps()} />);

      expect(
        screen.getByTestId("flow-builder-welcome-browse-more"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("flow-builder-welcome-template-simple-agent"),
      ).toBeNull();
    });

    it("should_offer_a_blank_flow_when_no_template_survives", () => {
      // Nothing to browse and nothing to start from, so the row collapses to
      // the one action left rather than three dead ends.
      useFlowsManagerStore.setState({ examples: [] });

      render(<FlowBuilderWelcome {...makeProps()} />);

      expect(
        screen.getByTestId("flow-builder-welcome-blank-flow"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("flow-builder-welcome-browse-more"),
      ).toBeNull();
      expect(screen.queryByText("Or start from a template:")).toBeNull();
    });

    it("should_land_on_the_blank_canvas_from_the_blank_flow_action", async () => {
      // The welcome already sits on a freshly created empty flow, so starting
      // blank is just dismissing the overlay onto it.
      useFlowsManagerStore.setState({ examples: [] });
      const props = makeProps();

      render(<FlowBuilderWelcome {...props} />);
      await userEvent.click(
        screen.getByTestId("flow-builder-welcome-blank-flow"),
      );

      expect(props.onClose).toHaveBeenCalledTimes(1);
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

    it("should_ignore_Escape_already_consumed_by_a_dialog_layer", () => {
      // Radix's DismissableLayer preventDefaults the Escape it uses to close
      // a dialog stacked above the welcome (e.g. the TemplatesModal) but the
      // event still bubbles to window; the welcome must not treat it as its
      // own dismissal, or one keypress closes both layers (LE-2041 QA).
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);
      const event = new KeyboardEvent("keydown", {
        key: "Escape",
        cancelable: true,
        bubbles: true,
      });
      event.preventDefault();
      window.dispatchEvent(event);
      expect(props.onClose).not.toHaveBeenCalled();
    });
  });
  describe("message length limit", () => {
    const typeInto = (value: string) => {
      const textarea = screen.getByTestId(
        "flow-builder-welcome-textarea",
      ) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value } });
      return textarea;
    };

    it("should_accept_a_prompt_far_past_the_old_500_character_cap", () => {
      // Regression: onChange sliced the value at 500 characters, so a longer
      // prompt lost its tail with nothing on screen to say so.
      render(<FlowBuilderWelcome {...makeProps()} />);

      const textarea = typeInto("a".repeat(1600));

      expect(textarea.value).toHaveLength(1600);
      expect(textarea).toHaveAttribute(
        "maxlength",
        String(DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH),
      );
    });

    it("should_always_show_the_character_count", () => {
      render(<FlowBuilderWelcome {...makeProps()} />);

      expect(
        screen.getByTestId("flow-builder-welcome-char-count"),
      ).toHaveTextContent(`0/${DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH}`);

      typeInto("a".repeat(120));

      expect(
        screen.getByTestId("flow-builder-welcome-char-count"),
      ).toHaveTextContent(`120/${DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH}`);
    });

    it("should_submit_a_prompt_at_the_configured_limit", () => {
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const prompt = "a".repeat(DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH);
      typeInto(prompt);
      fireEvent.click(screen.getByTestId("flow-builder-welcome-send-button"));

      expect(props.onSubmit).toHaveBeenCalledWith(prompt);
    });

    it("should_name_the_environment_variable_when_the_limit_is_reached", () => {
      render(<FlowBuilderWelcome {...makeProps()} />);

      const textarea = typeInto(
        "a".repeat(DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH),
      );

      const hint = screen.getByTestId("flow-builder-welcome-limit-hint");
      expect(hint).toBeVisible();
      expect(hint).toHaveTextContent("LANGFLOW_ASSISTANT_MAX_MESSAGE_LENGTH");
      expect(textarea).toHaveAttribute("aria-describedby", hint.id);
    });

    it("should_follow_the_limit_served_by_the_backend_config", () => {
      useUtilityStore.getState().setAssistantMaxMessageLength(6000);
      const props = makeProps();
      render(<FlowBuilderWelcome {...props} />);

      const prompt = "a".repeat(4000);
      const textarea = typeInto(prompt);

      expect(textarea).toHaveAttribute("maxlength", "6000");
      fireEvent.click(screen.getByTestId("flow-builder-welcome-send-button"));

      expect(props.onSubmit).toHaveBeenCalledWith(prompt);
    });
  });
});
