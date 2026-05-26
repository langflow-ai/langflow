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

describe("ErrorView — multi-card structure", () => {
  it("renders one error card inside the stack for a single block", () => {
    render(
      <ErrorView
        blocks={[makeErrorBlock("Boom A")]}
        showError={true}
        lastMessage={true}
        fitViewNode={jest.fn()}
        chat={baseChat}
      />,
    );

    expect(screen.getByTestId("error-card-stack")).toBeInTheDocument();
    expect(screen.getAllByTestId("error-card")).toHaveLength(1);
  });

  it("renders one error card per block, each as a direct child of the stack", () => {
    // Direct-child relationship is the behavioural guarantee that lets
    // the stack's spacing rule (whatever it is — gap utility today, CSS
    // module tomorrow) actually apply. If a future change wraps cards
    // in an extra div, the gap would silently break and this test fails
    // without us having to encode the Tailwind class names.
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

    const stack = screen.getByTestId("error-card-stack");
    const cards = screen.getAllByTestId("error-card");
    expect(cards).toHaveLength(3);
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
