import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppHeader from "../index";

// Mock stores and customization hooks to keep AppHeader lightweight in tests
jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector?: any) => {
    const state = { dark: false, setDark: jest.fn() };
    return selector ? selector(state) : state;
  },
}));

jest.mock("@/stores/logoStore", () => ({
  useLogoStore: (selector?: any) => {
    const state = { logoUrl: null, setLogoUrl: jest.fn() };
    return selector ? selector(state) : state;
  },
}));

jest.mock("@/customization/hooks/use-custom-theme", () => () => {});
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => (path: string) => path,
}));

// Mock app config query (logo), published flow, and agent by flow id
jest.mock("@/controllers/API/queries/application-config", () => ({
  useGetAppConfig: () => ({ data: undefined }),
}));

jest.mock("@/controllers/API/queries/published-flows", () => ({
  useGetPublishedFlow: (id?: string) => ({
    data: id ? { flow_name: "Published Flow Name" } : undefined,
  }),
}));

jest.mock(
  "@/controllers/API/queries/agent-marketplace/use-get-agent-by-flow-id",
  () => ({
    useGetAgentByFlowId: (params: { flow_id: string }) => ({
      data: params.flow_id
        ? { spec: { name: "Agent Spec Name" } }
        : undefined,
    }),
  }),
);

// Mock flows manager store to provide current flow name for flow route
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector?: any) => {
    const state = { currentFlow: { name: "My Flow", id: "flow-1" } };
    return selector ? selector(state) : state;
  },
}));

describe("AppHeader Breadcrumbs", () => {
  it("shows published flow name on marketplace detail", async () => {
    render(
      <MemoryRouter initialEntries={["/marketplace/detail/abc123"]}>
        <AppHeader />
      </MemoryRouter>,
    );

    expect(await screen.findByText("AI Studio")).toBeInTheDocument();
    expect(await screen.findByText("Marketplace")).toBeInTheDocument();
    expect(await screen.findByText("Published Flow Name")).toBeInTheDocument();
  });

  it("shows agent spec name on agent marketplace detail", async () => {
    render(
      <MemoryRouter initialEntries={["/agent-marketplace/detail/flow-42"]}>
        <AppHeader />
      </MemoryRouter>,
    );

    expect(await screen.findByText("AI Studio")).toBeInTheDocument();
    expect(await screen.findByText("Agent Marketplace")).toBeInTheDocument();
    expect(await screen.findByText("Agent Spec Name")).toBeInTheDocument();
  });

  it("falls back to state name when API missing", async () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: "/marketplace/detail/missing", state: { name: "From State" } }]}
      >
        <AppHeader />
      </MemoryRouter>,
    );

    expect(await screen.findByText("AI Studio")).toBeInTheDocument();
    expect(await screen.findByText("Marketplace")).toBeInTheDocument();
    expect(await screen.findByText("From State")).toBeInTheDocument();
  });

  it("does not affect other routes (e.g., flows)", async () => {
    render(
      <MemoryRouter initialEntries={["/flows"]}>
        <AppHeader />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Flows")).toBeInTheDocument();
  });

  it("shows AI Studio and flow name on flow page", async () => {
    render(
      <MemoryRouter initialEntries={["/flow/abc/folder/def"]}>
        <AppHeader />
      </MemoryRouter>,
    );

    expect(await screen.findByText("AI Studio")).toBeInTheDocument();
    expect(await screen.findByText("My Flow")).toBeInTheDocument();
  });
});