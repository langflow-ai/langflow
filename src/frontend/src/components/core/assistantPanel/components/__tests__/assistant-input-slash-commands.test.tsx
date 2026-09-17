import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH } from "@/constants/constants";
import { useUtilityStore } from "@/stores/utilityStore";
import { axe } from "@/utils/a11y-test";
import { AssistantInput } from "../assistant-input";

jest.mock("../../hooks/use-enabled-models", () => ({
  useEnabledModels: () => ({
    isCatalogReady: true,
    isModelEnabled: (model: unknown) => model !== null,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} aria-hidden="true" />;
  };
});

jest.mock("../model-selector", () => ({
  ModelSelector: () => <div data-testid="model-selector" />,
}));

jest.mock("../../helpers/messages", () => ({
  getRandomPlaceholderMessage: () => "Processing your request...",
}));

jest.mock("../../assistant-panel.constants", () => ({
  getAssistantPlaceholder: () => "Ask me anything about Langflow...",
}));

const MODEL = {
  id: "openai/gpt-4",
  name: "gpt-4",
  provider: "openai",
  displayName: "GPT-4",
};

function setup() {
  const onSend = jest.fn();
  const user = userEvent.setup();
  render(<AssistantInput onSend={onSend} onStop={jest.fn()} />);
  const textarea = screen.getByTestId(
    "assistant-input-textarea",
  ) as HTMLTextAreaElement;
  return { onSend, user, textarea };
}

const optionNames = () =>
  within(screen.getByRole("listbox", { name: "Assistant commands" }))
    .getAllByRole("option")
    .map((option) => option.getAttribute("data-command"));

describe("AssistantInput slash commands", () => {
  beforeAll(() => {
    // jsdom has no layout, so it does not implement scrollIntoView.
    Element.prototype.scrollIntoView = jest.fn();
  });

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(
      "langflow-assistant-selected-model",
      JSON.stringify(MODEL),
    );
    useUtilityStore
      .getState()
      .setAssistantMaxMessageLength(DEFAULT_ASSISTANT_MAX_MESSAGE_LENGTH);
  });

  it("should_list_every_command_when_slash_is_typed", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "/");

    expect(optionNames()).toEqual(["skip-all", "history", "iterations"]);
    expect(
      screen.getByText(
        "Toggle auto-approval of plans, flow proposals, and validated components",
      ),
    ).toBeInTheDocument();
  });

  it("should_show_each_argument_range_including_the_maximum", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "/");

    expect(
      screen.getByTestId("assistant-slash-command-option-iterations"),
    ).toHaveTextContent("[1–200 | off]");
    expect(
      screen.getByTestId("assistant-slash-command-option-history"),
    ).toHaveTextContent("[0–100 | off]");
  });

  it("should_narrow_the_list_as_the_command_is_typed", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "/it");

    expect(optionNames()).toEqual(["iterations"]);
  });

  it("should_move_the_highlight_with_arrow_keys_and_expose_it_to_assistive_tech", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "/");
    await user.keyboard("{ArrowDown}");

    const options = screen.getAllByRole("option");
    expect(options[1]).toHaveAttribute("aria-selected", "true");
    expect(textarea).toHaveAttribute("aria-activedescendant", options[1].id);
    expect(textarea).toHaveAttribute(
      "aria-controls",
      screen.getByRole("listbox").id,
    );

    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(screen.getAllByRole("option")[2]).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("should_insert_the_highlighted_command_on_enter_without_sending", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/");
    await user.keyboard("{ArrowDown}{Enter}");

    expect(textarea).toHaveValue("/history ");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(textarea).toHaveFocus();
  });

  it("should_send_the_inserted_command_on_a_second_enter", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/ite");
    await user.keyboard("{Enter}");
    await user.type(textarea, "60{Enter}");

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("/iterations 60", MODEL);
  });

  it("should_complete_the_command_on_tab_without_sending", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/ite");
    await user.keyboard("{Tab}");

    expect(textarea).toHaveValue("/iterations ");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(textarea).toHaveFocus();
  });

  it("should_send_the_typed_argument_after_completing", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/ite");
    await user.keyboard("{Tab}");
    await user.type(textarea, "60{Enter}");

    expect(onSend).toHaveBeenCalledWith("/iterations 60", MODEL);
  });

  it("should_insert_a_command_when_its_option_is_clicked", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/");
    await user.click(screen.getByRole("option", { name: /\/skip-all/ }));

    expect(textarea).toHaveValue("/skip-all");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("should_close_on_escape_and_keep_the_draft_and_focus", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/hi");
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(textarea).toHaveValue("/hi");
    expect(textarea).toHaveFocus();
    expect(textarea).not.toHaveAttribute("aria-activedescendant");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("should_not_let_escape_reach_page_hotkeys_that_close_the_panel", async () => {
    const pageEscapeHandler = jest.fn();
    document.addEventListener("keydown", pageEscapeHandler);
    try {
      const { user, textarea } = setup();

      await user.type(textarea, "/hi");
      await user.keyboard("{Escape}");

      expect(pageEscapeHandler).not.toHaveBeenCalledWith(
        expect.objectContaining({ key: "Escape" }),
      );
    } finally {
      document.removeEventListener("keydown", pageEscapeHandler);
    }
  });

  it("should_send_an_unknown_slash_prompt_as_typed", async () => {
    const { onSend, user, textarea } = setup();

    await user.type(textarea, "/zzz");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.keyDown(textarea, { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("/zzz", MODEL);
  });

  it("should_not_open_for_a_slash_inside_a_prompt", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "use a/b path");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("should_not_recall_input_history_while_the_menu_is_open", async () => {
    localStorage.setItem(
      "langflow-assistant-input-history",
      JSON.stringify(["previous prompt"]),
    );
    const { user, textarea } = setup();

    await user.type(textarea, "/");
    await user.keyboard("{ArrowUp}");

    expect(textarea).toHaveValue("/");
  });

  it("should_have_no_axe_violations_while_the_menu_is_open", async () => {
    const { user, textarea } = setup();

    await user.type(textarea, "/");
    await user.keyboard("{ArrowDown}");

    // `region` is a page-level landmark rule that a bare component render cannot satisfy;
    // the Playwright live-DOM scan covers the composer inside the real page.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });
});
