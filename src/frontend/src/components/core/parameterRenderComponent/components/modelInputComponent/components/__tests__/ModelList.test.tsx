import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Command } from "@/components/ui/command";
import type { ModelOption } from "../../types";
import ModelList, { getModelOptionTestId } from "../ModelList";

// cmdk calls this internally when its selection/keyboard state changes.
Element.prototype.scrollIntoView = jest.fn();

// ModelList's CommandItem/CommandGroup/CommandList rely on cmdk's own
// Command context (grouping, filtering, keyboard nav) — rendering them
// without a <Command> ancestor throws, so every test wraps in one. This is
// still far lighter than mounting the full ModelInputComponent tree (no
// QueryClientProvider, no store/API mocks): ModelList itself is pure
// presentational, driven entirely by its own props.
const renderList = (props: {
  groupedOptions: Record<string, ModelOption[]>;
  selectedModel: ModelOption | null;
  onSelect: (modelName: string, provider: string) => void;
}) => render(<Command>{<ModelList {...props} />}</Command>);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className} />
  ),
}));

const gpt4: ModelOption = {
  name: "gpt-4",
  icon: "Bot",
  provider: "OpenAI",
  metadata: {},
};
const claude: ModelOption = {
  name: "claude-3-opus",
  icon: "Bot",
  provider: "Anthropic",
  metadata: {},
};

describe("ModelList — empty state", () => {
  it("shows the no-models-enabled message and no options when groupedOptions is empty", () => {
    renderList({
      groupedOptions: {},
      selectedModel: null,
      onSelect: jest.fn(),
    });

    const placeholder = screen.getByText("No Models Enabled");
    expect(placeholder).toBeInTheDocument();
    // The one and only option is the disabled placeholder itself — not a
    // real, selectable model.
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(placeholder.closest('[role="option"]')).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });
});

describe("ModelList — grouping", () => {
  it("renders one CommandGroup heading per provider", () => {
    renderList({
      groupedOptions: { OpenAI: [gpt4], Anthropic: [claude] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(
      screen.getByTestId(getModelOptionTestId("OpenAI", "gpt-4")),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(getModelOptionTestId("Anthropic", "claude-3-opus")),
    ).toBeInTheDocument();
  });
});

describe("ModelList — deprecated badge", () => {
  it("shows a Deprecated badge for a deprecated model", () => {
    const deprecated: ModelOption = {
      ...gpt4,
      metadata: { deprecated: true },
    };
    renderList({
      groupedOptions: { OpenAI: [deprecated] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(screen.getByTestId("gpt-4-deprecated-badge")).toBeInTheDocument();
  });

  it("does not render a badge for a non-deprecated model", () => {
    renderList({
      groupedOptions: { OpenAI: [gpt4] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(
      screen.queryByTestId("gpt-4-deprecated-badge"),
    ).not.toBeInTheDocument();
  });
});

describe("ModelList — icon fallback", () => {
  it("uses the model's own icon when present", () => {
    renderList({
      groupedOptions: { OpenAI: [{ ...gpt4, icon: "OpenAI" }] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(
      screen
        .getByTestId(getModelOptionTestId("OpenAI", "gpt-4"))
        .querySelector('[data-testid="icon-OpenAI"]'),
    ).toBeInTheDocument();
  });

  it("falls back to the Bot icon when the model has no icon", () => {
    renderList({
      groupedOptions: { OpenAI: [{ ...gpt4, icon: "" }] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(
      screen
        .getByTestId(getModelOptionTestId("OpenAI", "gpt-4"))
        .querySelector('[data-testid="icon-Bot"]'),
    ).toBeInTheDocument();
  });
});

describe("ModelList — selection state", () => {
  // Regression guard: models can share a name across providers (e.g.
  // "gpt-4o" via OpenAI directly vs. via Azure AI Foundry) — the check icon
  // must match on name AND provider together, not name alone.
  it("marks only the option matching both name and provider as selected", () => {
    const openAiGpt4o: ModelOption = {
      name: "gpt-4o",
      icon: "Bot",
      provider: "OpenAI",
      metadata: {},
    };
    const azureGpt4o: ModelOption = {
      name: "gpt-4o",
      icon: "Bot",
      provider: "Azure AI Foundry",
      metadata: {},
    };
    renderList({
      groupedOptions: {
        OpenAI: [openAiGpt4o],
        "Azure AI Foundry": [azureGpt4o],
      },
      selectedModel: azureGpt4o,
      onSelect: jest.fn(),
    });

    expect(
      screen
        .getByTestId(getModelOptionTestId("Azure AI Foundry", "gpt-4o"))
        .querySelector('[data-testid="icon-Check"]'),
    ).toHaveClass("opacity-100");
    expect(
      screen
        .getByTestId(getModelOptionTestId("OpenAI", "gpt-4o"))
        .querySelector('[data-testid="icon-Check"]'),
    ).toHaveClass("opacity-0");
  });

  it("marks no option as selected when selectedModel is null", () => {
    renderList({
      groupedOptions: { OpenAI: [gpt4] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    expect(
      screen
        .getByTestId(getModelOptionTestId("OpenAI", "gpt-4"))
        .querySelector('[data-testid="icon-Check"]'),
    ).toHaveClass("opacity-0");
  });
});

describe("ModelList — selecting an option", () => {
  it("calls onSelect with the model name and provider", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    renderList({
      groupedOptions: { OpenAI: [gpt4] },
      selectedModel: null,
      onSelect,
    });

    await user.click(
      screen.getByTestId(getModelOptionTestId("OpenAI", "gpt-4")),
    );

    expect(onSelect).toHaveBeenCalledWith("gpt-4", "OpenAI");
  });
});

describe("ModelList — position announcement", () => {
  it("computes the sr-only N of M text across all providers combined", () => {
    renderList({
      groupedOptions: { OpenAI: [gpt4], Anthropic: [claude] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    const first = screen.getByTestId(getModelOptionTestId("OpenAI", "gpt-4"));
    const second = screen.getByTestId(
      getModelOptionTestId("Anthropic", "claude-3-opus"),
    );

    expect(first).toHaveAccessibleName(/1 of 2/);
    expect(second).toHaveAccessibleName(/2 of 2/);
  });

  // Regression guard: aria-posinset/aria-setsize were dropped entirely —
  // NVDA/JAWS honor them (unlike VoiceOver), which doubled the "N of M"
  // announcement alongside the sr-only text. Only the sr-only text remains,
  // since it's the one mechanism that works across all screen readers.
  it("does not set aria-posinset/aria-setsize", () => {
    renderList({
      groupedOptions: { OpenAI: [gpt4], Anthropic: [claude] },
      selectedModel: null,
      onSelect: jest.fn(),
    });

    const first = screen.getByTestId(getModelOptionTestId("OpenAI", "gpt-4"));
    expect(first).not.toHaveAttribute("aria-posinset");
    expect(first).not.toHaveAttribute("aria-setsize");
  });
});
