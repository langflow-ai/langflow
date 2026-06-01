import { render, screen } from "@testing-library/react";
import type { ContentBlockItem } from "@/types/chat";
import ContentDisplay from "../ContentDisplay";

// react-markdown ships ESM that jest doesn't transpile by default; the
// MarkdownComponent only matters for text/error/json/code cases, none of
// which these tests touch.
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("rehype-mathjax/browser", () => () => {});
jest.mock("remark-gfm", () => () => {});
// Mocks use module identifiers as the importer (ContentDisplay) sees them,
// which is why these paths are relative to ContentDisplay.tsx (one dir up
// from this test file), not to the test file itself.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));
jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="code-tabs" />,
}));
jest.mock("../DurationDisplay", () => ({
  __esModule: true,
  default: () => <div data-testid="duration" />,
}));

describe("ContentDisplay", () => {
  describe("usage", () => {
    it("hides the 'Tokens:' label when both counts are null", () => {
      // Backend Optional[int] serializes as null when absent. Regression
      // guard: previously rendered the literal string 'null in / null out'
      // because the check used `!== undefined`.
      const usage = {
        type: "usage",
        model: "gpt-4o",
        input_tokens: null,
        output_tokens: null,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={usage} chatId="t1" />);
      expect(screen.queryByText(/Tokens:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/null/)).not.toBeInTheDocument();
      expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    });

    it("renders both counts when they are zero", () => {
      // 0 is a legitimate count; `!= null` keeps it, `!== undefined` would
      // also keep it. This is a forward-compat guard for future refactors.
      const usage = {
        type: "usage",
        model: "claude",
        input_tokens: 0,
        output_tokens: 0,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={usage} chatId="t2" />);
      expect(screen.getByText(/0 in/)).toBeInTheDocument();
      expect(screen.getByText(/0 out/)).toBeInTheDocument();
    });

    it("renders only the input count when output is null", () => {
      const usage = {
        type: "usage",
        input_tokens: 42,
        output_tokens: null,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={usage} chatId="t3" />);
      const span = screen.getByText(/Tokens:/);
      expect(span).toHaveTextContent("Tokens: 42 in");
      expect(span).not.toHaveTextContent("null");
    });
  });

  describe("image", () => {
    it("renders the base64 fallback when urls contains only empty strings", () => {
      // Regression guard: previously suppressed base64 whenever urls had any
      // length, so urls=[''] killed the working fallback.
      const image = {
        type: "image",
        urls: [""],
        base64: "AAAA",
        mime_type: "image/png",
        caption: "fallback",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={image} chatId="t4" />);
      const imgs = screen.getAllByRole("img");
      const base64Img = imgs.find((img) =>
        (img as HTMLImageElement).src.startsWith("data:image/png;base64,"),
      );
      expect(base64Img).toBeDefined();
    });

    it("does not duplicate the image when a valid URL and base64 are both set", () => {
      const image = {
        type: "image",
        urls: ["https://example.com/a.png"],
        base64: "AAAA",
        mime_type: "image/png",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={image} chatId="t5" />);
      const imgs = screen.getAllByRole("img");
      const base64Img = imgs.find((img) =>
        (img as HTMLImageElement).src.startsWith("data:"),
      );
      expect(base64Img).toBeUndefined();
      expect(imgs).toHaveLength(1);
    });
  });

  describe("reasoning", () => {
    it("shows a 'Thinking…' shimmer while the duration is absent", () => {
      // No duration on the content means the producer is still emitting
      // reasoning chunks. The renderer should show a live indicator
      // rather than the resolved summary.
      const reasoning = {
        type: "reasoning",
        text: "Considering options...",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={reasoning} chatId="t-r1" />);
      const label = screen.getByText(/Thinking/i);
      expect(label).toBeInTheDocument();
      // Live label gets animate-pulse so the user sees it as in-flight.
      expect(label.className).toMatch(/animate-pulse/);
    });

    it("collapses by default with a 'Thought for …' summary when duration is set", () => {
      const reasoning = {
        type: "reasoning",
        text: "I checked the docs and decided to call the weather tool.",
        duration: 3200,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={reasoning} chatId="t-r2" />);
      expect(screen.getByText(/Thought for/)).toBeInTheDocument();
      // Body stays collapsed until the user clicks the summary trigger.
      expect(screen.queryByText(/I checked the docs/)).not.toBeInTheDocument();
    });
  });

  describe("renderDuration", () => {
    it("renders the top-right duration for a non-reasoning block", () => {
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: {},
        duration: 1200,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-d1" />);
      expect(screen.getByTestId("duration")).toBeInTheDocument();
    });

    it("skips the top-right duration for reasoning to avoid double render", () => {
      // ReasoningDisplay already surfaces the duration inline as
      // "Thought for Xs"; the absolute top-right DurationDisplay must be
      // skipped for reasoning so it doesn't render twice.
      const reasoning = {
        type: "reasoning",
        text: "Decided to call the weather tool.",
        duration: 3200,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={reasoning} chatId="t-d2" />);
      expect(screen.getByText(/Thought for/)).toBeInTheDocument();
      expect(screen.queryByTestId("duration")).not.toBeInTheDocument();
    });
  });

  describe("tool_use", () => {
    it("reads input from the 'input' alias when the backend dumped by_alias=True", () => {
      // The Python ToolContent.tool_input field has alias="input"; AG-UI
      // and other serialization paths emit by_alias=True, so the stored
      // shape uses `input` not `tool_input`. Renderer must fall back.
      const tool = {
        type: "tool_use",
        name: "fetch_content",
        input: { urls: ["https://langflow.org"] },
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-alias" />);
      expect(screen.getByText("urls")).toBeInTheDocument();
      expect(screen.queryByText(/no arguments/)).not.toBeInTheDocument();
    });

    it("renders flat input as key/value rows, not JSON", () => {
      // {query: "weather", units: "metric"} is a flat object — easier to
      // scan as two rows than as JSON with braces and quotes.
      const tool = {
        type: "tool_use",
        name: "weather",
        tool_input: { query: "weather", units: "metric" },
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t2" />);
      expect(screen.getByText("query")).toBeInTheDocument();
      expect(screen.getByText('"weather"')).toBeInTheDocument();
      expect(screen.getByText("units")).toBeInTheDocument();
      expect(screen.getByText('"metric"')).toBeInTheDocument();
      // No JSON code block for the flat case.
      expect(screen.queryByTestId("code-tabs")).not.toBeInTheDocument();
    });

    it("falls back to JSON block when input has nested values", () => {
      // Nested object would be ugly in row form — code block keeps it
      // readable and copyable.
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: { filters: { min: 1, max: 10 } },
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t3" />);
      expect(screen.getByTestId("code-tabs")).toBeInTheDocument();
    });

    it("unwraps a LangChain ToolMessage-shaped output to render only its content", () => {
      // Backend tools return {content, name, id, tool_call_id, status} —
      // the LangChain ToolMessage shape. The metadata is duplicated by
      // the accordion trigger; only `content` is interesting to show.
      const tool = {
        type: "tool_use",
        name: "fetch_content",
        tool_input: {},
        output: {
          content: "the readable body",
          name: "fetch_content",
          id: "abc-123",
          tool_call_id: "toolu_xyz",
          status: "success",
        },
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-unwrap" />);
      expect(screen.getByText(/the readable body/)).toBeInTheDocument();
      // Plumbing metadata should not be rendered.
      expect(screen.queryByText(/toolu_xyz/)).not.toBeInTheDocument();
      expect(screen.queryByText(/abc-123/)).not.toBeInTheDocument();
    });

    it("routes pre-formatted string output through the code tab (not markdown)", () => {
      // Pandas df.to_string() style output has wide column padding that
      // markdown rendering would mangle. Detection should kick it into
      // the monospace code-tab path instead.
      const tool = {
        type: "tool_use",
        name: "df_describe",
        tool_input: {},
        output:
          "                                                text                   url\n" +
          "0  Langflow | Low-code AI builder for agentic...  https://langflow.org",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-pre" />);
      expect(screen.getByTestId("code-tabs")).toBeInTheDocument();
    });

    it("hides the OUTPUT section entirely when output is null", () => {
      // output: null still rendered a visible 'OUTPUT' eyebrow with no
      // body. Treat null the same as undefined so the empty section
      // doesn't render at all.
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: {},
        output: null,
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-null" />);
      expect(screen.queryByText("OUTPUT")).not.toBeInTheDocument();
    });

    it("hides the output section when output is an empty string", () => {
      // An empty (or whitespace-only) string output used to render an empty
      // bordered box. Treat it as no output so nothing renders. The output
      // box is the only `.max-h-96 overflow-auto` element here.
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: {},
        output: "   ",
      } as unknown as ContentBlockItem;
      const { container } = render(
        <ContentDisplay content={tool} chatId="t-t-empty-out" />,
      );
      expect(container.querySelector(".max-h-96")).toBeNull();
    });

    it("keeps the JSON block when output has extra fields beyond ToolMessage", () => {
      // Don't unwrap if the producer added fields the user might need —
      // could be tool-specific data the renderer shouldn't drop silently.
      const tool = {
        type: "tool_use",
        name: "fetch_content",
        tool_input: {},
        output: {
          content: "the body",
          custom_field: 42,
        },
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-no-unwrap" />);
      // Falls through to the JSON code block (mocked as code-tabs).
      expect(screen.getByTestId("code-tabs")).toBeInTheDocument();
    });

    it("renders the error body in a destructive-toned panel", () => {
      // No eyebrow label — the surrounding accordion already says
      // "tool call" and the destructive bg + color carries the meaning.
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: {},
        error: "boom",
      } as unknown as ContentBlockItem;
      const { container } = render(
        <ContentDisplay content={tool} chatId="t-t-err" />,
      );
      // The destructive panel wraps the code tab.
      expect(container.querySelector(".bg-destructive\\/10")).toBeTruthy();
    });

    it("renders nothing for empty input (no 'no arguments' placeholder)", () => {
      // The surrounding accordion provides enough context; an explicit
      // empty-state line just adds chrome. The OUTPUT below carries the
      // useful information.
      const tool = {
        type: "tool_use",
        name: "search",
        tool_input: {},
        output: "hi",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={tool} chatId="t-t-empty-input" />);
      expect(screen.queryByText(/no arguments/)).not.toBeInTheDocument();
    });
  });

  describe("citation", () => {
    it("renders the domain extracted from the URL alongside the title", () => {
      const citation = {
        type: "citation",
        url: "https://docs.python.org/3/library/typing.html",
        title: "typing — Support for type hints",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={citation} chatId="t-c1" />);
      expect(screen.getByText(/docs\.python\.org/)).toBeInTheDocument();
      expect(
        screen.getByText("typing — Support for type hints"),
      ).toBeInTheDocument();
    });

    it("does not render an anchor for non-http URLs (sanitization)", () => {
      // javascript: and other non-http(s) schemes must never become a
      // clickable link; we degrade to a text-only card instead.
      const citation = {
        type: "citation",
        url: "javascript:alert(1)",
        title: "bad",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={citation} chatId="t-c2" />);
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
      expect(screen.getByText("bad")).toBeInTheDocument();
    });

    it("renders the cited_text snippet as plain text, not HTML", () => {
      // The cited_text comes from upstream model output and may contain
      // angle brackets. React text nodes escape them, so the literal
      // characters render rather than parsing as markup.
      const citation = {
        type: "citation",
        url: "https://example.com",
        title: "src",
        cited_text: "<script>alert(1)</script>",
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={citation} chatId="t-c3" />);
      expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    });
  });

  describe("group", () => {
    it("renders the title and recurses through nested contents", () => {
      // Nested ContentBlock inside another container: previously fell
      // through ContentDisplay's switch and rendered nothing. Two visible
      // children prove recursion: usage and citation both render text
      // directly without a reveal-on-click behavior.
      const nested = {
        type: "group",
        title: "Inner step",
        contents: [
          { type: "usage", input_tokens: 1, output_tokens: 2 },
          {
            type: "citation",
            url: "https://example.com",
            title: "Cited source",
          },
        ],
      } as unknown as ContentBlockItem;
      render(<ContentDisplay content={nested} chatId="t6" />);
      expect(screen.getByText("Inner step")).toBeInTheDocument();
      expect(screen.getByText(/Tokens: 1 in \/ 2 out/)).toBeInTheDocument();
      expect(screen.getByText("Cited source")).toBeInTheDocument();
    });
  });
});
