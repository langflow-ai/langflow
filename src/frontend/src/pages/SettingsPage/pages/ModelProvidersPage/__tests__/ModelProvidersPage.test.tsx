import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import ModelProvidersPage from "../ModelProvidersPage";

// Mock the child components
jest.mock("../components/model-providers-header", () => {
  return function MockModelProvidersHeader() {
    return <div data-testid="model-providers-header">Model Providers Header</div>;
  };
});

jest.mock("../components/provider-list", () => {
  return function MockProviderList({ type }: { type: string }) {
    return <div data-testid={`provider-list-${type}`}>Provider List: {type}</div>;
  };
});

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe("ModelProvidersPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    render(<ModelProvidersPage />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("model-providers-header")).toBeInTheDocument();
  });

  it("renders the header component", () => {
    render(<ModelProvidersPage />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("model-providers-header")).toBeInTheDocument();
    expect(screen.getByText("Model Providers Header")).toBeInTheDocument();
  });

  it("renders the enabled provider list", () => {
    render(<ModelProvidersPage />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("provider-list-enabled")).toBeInTheDocument();
    expect(screen.getByText("Provider List: enabled")).toBeInTheDocument();
  });

  it("renders the available provider list", () => {
    render(<ModelProvidersPage />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("provider-list-available")).toBeInTheDocument();
    expect(screen.getByText("Provider List: available")).toBeInTheDocument();
  });

  it("renders all required child components", () => {
    render(<ModelProvidersPage />, { wrapper: createTestWrapper() });

    // Should render header
    expect(screen.getByTestId("model-providers-header")).toBeInTheDocument();

    // Should render both provider lists
    expect(screen.getByTestId("provider-list-enabled")).toBeInTheDocument();
    expect(screen.getByTestId("provider-list-available")).toBeInTheDocument();
  });

  it("has correct layout structure", () => {
    const { container } = render(<ModelProvidersPage />, {
      wrapper: createTestWrapper()
    });

    const mainDiv = container.firstChild as HTMLElement;
    expect(mainDiv).toHaveClass("flex");
    expect(mainDiv).toHaveClass("h-full");
    expect(mainDiv).toHaveClass("w-full");
    expect(mainDiv).toHaveClass("flex-col");
    expect(mainDiv).toHaveClass("gap-6");
    expect(mainDiv).toHaveClass("overflow-x-hidden");
  });

  it("renders components in the correct order", () => {
    const { container } = render(<ModelProvidersPage />, {
      wrapper: createTestWrapper()
    });

    const mainDiv = container.firstChild as HTMLElement;
    const children = Array.from(mainDiv.children);

    // First child should be header
    expect(children[0]).toHaveAttribute("data-testid", "model-providers-header");

    // Second child should be enabled provider list
    expect(children[1]).toHaveAttribute("data-testid", "provider-list-enabled");

    // Third child should be available provider list
    expect(children[2]).toHaveAttribute("data-testid", "provider-list-available");
  });
});
