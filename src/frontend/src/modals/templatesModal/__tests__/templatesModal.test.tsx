import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import TemplatesModal from "../index";

const navProps: Array<Record<string, unknown>> = [];

jest.mock("react-router-dom", () => ({
  useParams: () => ({}),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(() => Promise.resolve("flow-id")),
}));

jest.mock("../../baseModal", () => {
  const BaseModal = Object.assign(
    ({ children }: { children: ReactNode }) => <>{children}</>,
    {
      Content: ({ children }: { children: ReactNode }) => <>{children}</>,
      Footer: ({ children }: { children: ReactNode }) => <>{children}</>,
    },
  );

  return {
    __esModule: true,
    default: BaseModal,
  };
});

jest.mock("../components/navComponent", () => ({
  Nav: (props: Record<string, unknown>) => {
    navProps.push(props);
    return <div data-testid="templates-nav" />;
  },
}));

jest.mock("../components/GetStartedComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="get-started-component" />,
}));

jest.mock("../components/TemplateContentComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="template-content-component" />,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

const example = (overrides: Record<string, unknown>) =>
  ({ id: String(overrides.name_key ?? overrides.name), ...overrides }) as never;

/** Enough templates that every nav tab has something behind it. */
const FULL_CATALOG = [
  example({
    name: "Basic Prompting",
    name_key: "basic_prompting",
    tags: ["chatbots"],
  }),
  example({
    name: "Vector Store RAG",
    name_key: "vector_store_rag",
    tags: ["rag"],
  }),
  example({ name: "Simple Agent", name_key: "simple_agent", tags: ["agents"] }),
  example({ name: "Assistant", tags: ["assistants"] }),
  example({ name: "Classifier", tags: ["classification"] }),
  example({ name: "Coder", tags: ["coding"] }),
  example({ name: "Writer", tags: ["content-generation"] }),
  example({ name: "Q and A", tags: ["q-a"] }),
];

const visibleTabIds = () => {
  const categories = navProps.at(-1)?.categories as Array<{
    items: Array<{ id: string }>;
  }>;
  return categories.flatMap((category) =>
    category.items.map((item) => item.id),
  );
};

const visibleGroups = () =>
  (navProps.at(-1)?.categories as Array<{ title: string }>).map(
    (category) => category.title,
  );

describe("TemplatesModal", () => {
  beforeEach(() => {
    navProps.length = 0;
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: false });
      useFlowsManagerStore.setState({ examples: FULL_CATALOG });
    });
  });

  afterEach(() => {
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: false });
    });
  });

  it("passes the effective tab to the nav when starter projects are hidden", () => {
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: true });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(screen.getByTestId("templates-nav")).toBeInTheDocument();
    expect(navProps.at(-1)?.currentTab).toBe("all-templates");

    const categories = navProps.at(-1)?.categories as
      | Array<{ items: Array<{ id: string }> }>
      | undefined;

    const categoryItemIds =
      categories?.flatMap((category) =>
        category.items.map((item) => item.id),
      ) ?? [];

    expect(categoryItemIds).not.toContain("get-started");
  });

  it("keeps get-started selected in the nav when starter projects are visible", () => {
    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(screen.getByTestId("templates-nav")).toBeInTheDocument();
    expect(navProps.at(-1)?.currentTab).toBe("get-started");
  });

  it("keeps every tab while the catalog is intact", () => {
    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(visibleTabIds()).toEqual([
      "get-started",
      "all-templates",
      "assistants",
      "classification",
      "coding",
      "content-generation",
      "q-a",
      "chatbots",
      "rag",
      "agents",
    ]);
  });

  it("hides only the tabs a policy emptied", () => {
    // One RAG template survives, so that tab stays while the rest go.
    act(() => {
      useFlowsManagerStore.setState({
        examples: [example({ name: "Vector Store RAG", tags: ["rag"] })],
      });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(visibleTabIds()).toEqual(["all-templates", "rag"]);
  });

  it("drops a group heading once its last tab goes", () => {
    // "Use Cases" would otherwise render as a heading over nothing.
    act(() => {
      useFlowsManagerStore.setState({
        examples: [example({ name: "Vector Store RAG", tags: ["rag"] })],
      });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(visibleGroups()).not.toContain("Use Cases");
    expect(visibleGroups()).toContain("Methodology");
  });

  it("moves off get-started when a policy blocks every featured card", () => {
    // Opening a disabled tab would show the empty pane the design replaces.
    act(() => {
      useFlowsManagerStore.setState({
        examples: [example({ name: "Vector Store RAG", tags: ["rag"] })],
      });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(navProps.at(-1)?.currentTab).toBe("all-templates");
    expect(
      screen.getByTestId("template-content-component"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("get-started-component"),
    ).not.toBeInTheDocument();
  });

  it("falls back to the whole-catalog listing when nothing survives", () => {
    // Every tab is disabled, so the pane must still explain the empty catalog
    // rather than showing the featured-cards tab with nothing in it.
    act(() => {
      useFlowsManagerStore.setState({ examples: [] });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(navProps.at(-1)?.currentTab).toBe("all-templates");
    expect(visibleTabIds()).toEqual([]);
    expect(
      screen.getByTestId("template-content-component"),
    ).toBeInTheDocument();
  });
});
