import { render, screen } from "@testing-library/react";
import type { ChatMessageType, ContentBlock } from "@/types/chat";
import { ErrorView } from "../error-message";

jest.mock("@/components/common/genericIconComponent", () => {
  const Icon = ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  );
  return { __esModule: true, default: Icon, ForwardedIconComponent: Icon };
});

jest.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  motion: {
    div: (props: React.HTMLAttributes<HTMLDivElement>) => <div {...props} />,
  },
}));

jest.mock("@/components/ui/accordion", () => ({
  Accordion: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion">{children}</div>
  ),
  AccordionItem: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion-item">{children}</div>
  ),
  AccordionTrigger: ({ children }: { children: React.ReactNode }) => (
    <button type="button" data-testid="accordion-trigger">
      {children}
    </button>
  ),
  AccordionContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion-content">{children}</div>
  ),
}));

jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="code-tabs" />,
}));

jest.mock("@/components/ui/TextShimmer", () => ({
  TextShimmer: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

jest.mock("../../utils/extract-error-message", () => ({
  extractErrorMessage: (reason: string) => reason,
}));

const makeErrorBlock = (reason: string): ContentBlock => ({
  title: "error",
  allow_markdown: true,
  component: "Component",
  contents: [
    {
      type: "error",
      reason,
      component: "Component",
      field: "field",
      duration: 0,
      header: { title: "Error", icon: "AlertCircle" },
    },
  ],
});

const baseChat: ChatMessageType = {
  message: "",
  isSend: false,
  sender_name: "Machine",
  session: "flow-1",
  properties: { source: { id: "node-1" } },
} as unknown as ChatMessageType;

describe("ErrorView — multi-card spacing", () => {
  it("renders a single error card inside the gap-aware stack", () => {
    render(
      <ErrorView
        blocks={[makeErrorBlock("Boom A")]}
        showError={true}
        lastMessage={true}
        fitViewNode={jest.fn()}
        chat={baseChat}
      />,
    );

    const stack = screen.getByTestId("error-card-stack");
    expect(stack).toBeInTheDocument();
    expect(stack.className).toContain("flex");
    expect(stack.className).toContain("flex-col");
    expect(stack.className).toContain("gap-2");
    expect(screen.getAllByTestId("error-card")).toHaveLength(1);
  });

  it("renders each error block as its own card inside the gap stack", () => {
    render(
      <ErrorView
        blocks={[
          makeErrorBlock("Boom A"),
          makeErrorBlock("Boom B"),
          makeErrorBlock("Boom C"),
        ]}
        showError={true}
        lastMessage={true}
        fitViewNode={jest.fn()}
        chat={baseChat}
      />,
    );

    const cards = screen.getAllByTestId("error-card");
    expect(cards).toHaveLength(3);
    const stack = screen.getByTestId("error-card-stack");
    expect(stack.className).toContain("gap-2");
    // Each card must be a direct child of the stack so the gap utility
    // applies. (Wrapping a card in an extra div would defeat the gap.)
    cards.forEach((card) => {
      expect(card.parentElement).toBe(stack);
    });
  });

  it("does not render the error stack while the loading state is shown", () => {
    render(
      <ErrorView
        blocks={[makeErrorBlock("Boom A")]}
        showError={false}
        lastMessage={true}
        fitViewNode={jest.fn()}
        chat={baseChat}
      />,
    );

    expect(screen.queryByTestId("error-card-stack")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-card")).not.toBeInTheDocument();
  });
});
