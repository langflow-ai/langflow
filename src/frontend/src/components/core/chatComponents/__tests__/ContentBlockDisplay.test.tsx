import { render, screen } from "@testing-library/react";
import type { ContentBlockItem } from "@/types/chat";
import { ContentBlockDisplay } from "../ContentBlockDisplay";

// react-markdown ships ESM jest doesn't transpile; passthrough so any text
// rendered by ContentDisplay still lands in the DOM as plain children. Same
// infra mocks the sibling ContentDisplay.test.tsx uses. Everything else
// (ContentBlockDisplay, ContentDisplay, ToolCallCard, SourcesStrip, the Radix
// accordion, framer-motion, useToolDurations) renders for real — these are
// integration probes, not unit stubs.
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("rehype-mathjax/browser", () => () => {});
jest.mock("remark-gfm", () => () => {});
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

// Cast helpers: the fixtures intentionally model the on-the-wire shapes
// (including the untyped legacy group), so they bypass the strict union.
const cb = (x: unknown): ContentBlockItem => x as ContentBlockItem;
const blocks = (xs: unknown[]): ContentBlockItem[] => xs.map(cb);

const tool = (name: string) => ({ type: "tool_use", name });
const text = (t: string) => ({ type: "text", text: t });
const usage = () => ({ type: "usage", input_tokens: 5, output_tokens: 9 });
const citation = (title: string, url = "https://example.com/a") => ({
  type: "citation",
  title,
  url,
});
const media = (urls = ["https://example.com/x.png"]) => ({
  type: "media",
  urls,
});
const group = (contents: unknown[]) => ({
  type: "group",
  title: "Agent Steps",
  contents,
});
// Legacy / v1-projected group: persisted without the `type` discriminator.
const untypedGroup = (contents: unknown[]) => ({
  title: "Agent Steps",
  contents,
});

describe("ContentBlockDisplay deep probes", () => {
  describe("the fix: a group's displayable non-tool content renders", () => {
    it("renders a tool-less group's citation (previously dropped to null)", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([group([citation("Probe Citation")])])}
          chatId="p1"
        />,
      );
      expect(screen.getByText("Probe Citation")).toBeInTheDocument();
    });

    it("renders a tool-less group's media image", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([group([media()])])}
          chatId="p2"
        />,
      );
      expect(screen.getByRole("img")).toHaveAttribute(
        "src",
        "https://example.com/x.png",
      );
    });

    it("renders non-tool content from an UNTYPED legacy group", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([
            untypedGroup([tool("search"), citation("Untyped Probe")]),
          ])}
          chatId="p3"
        />,
      );
      expect(screen.getByText("Untyped Probe")).toBeInTheDocument();
    });

    it("renders both the tool and a non-tool leaf in a tool-bearing group", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([
            group([tool("grp_tool"), citation("Side Cite")]),
          ])}
          chatId="p4"
          hideHeader
        />,
      );
      expect(screen.getByText("Side Cite")).toBeInTheDocument();
      expect(screen.getByText("GRP TOOL")).toBeInTheDocument();
    });
  });

  describe("no regression: legacy scaffolding stays hidden", () => {
    it("hides a legacy group's Input/Output text but shows its tool", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([
            group([
              text("INPUT_SCAFFOLD"),
              tool("search_tool"),
              text("OUTPUT_SCAFFOLD"),
            ]),
          ])}
          chatId="p5"
          hideHeader
        />,
      );
      expect(screen.queryByText("INPUT_SCAFFOLD")).not.toBeInTheDocument();
      expect(screen.queryByText("OUTPUT_SCAFFOLD")).not.toBeInTheDocument();
      expect(screen.getByText("SEARCH TOOL")).toBeInTheDocument();
    });

    it("renders nothing for a text-only group", () => {
      const { container } = render(
        <ContentBlockDisplay
          contentBlocks={blocks([group([text("ONLY_SCAFFOLD")])])}
          chatId="p6"
        />,
      );
      expect(screen.queryByText("ONLY_SCAFFOLD")).not.toBeInTheDocument();
      expect(container).toBeEmptyDOMElement();
    });

    it("renders nothing for a group of only usage metadata", () => {
      const { container } = render(
        <ContentBlockDisplay
          contentBlocks={blocks([group([usage()])])}
          chatId="p7"
        />,
      );
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("flat shape unchanged", () => {
    it("renders top-level flat leaves as before (no groups)", () => {
      render(
        <ContentBlockDisplay
          contentBlocks={blocks([tool("flat_tool"), citation("Flat Cite")])}
          chatId="p8"
        />,
      );
      expect(screen.getByText("FLAT TOOL")).toBeInTheDocument();
      expect(screen.getByText("Flat Cite")).toBeInTheDocument();
    });
  });
});
