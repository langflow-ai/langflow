import { render, screen } from "@testing-library/react";
import ModelSelection from "../components/ModelSelection";
import { Model } from "../components/types";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Mock enabled models hook
jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: { enabled_models: {} },
    isLoading: false,
    isSuccess: true,
    isFetching: false,
    isFetchedAfterMount: true,
    fetchStatus: "idle",
  })),
}));

const someModels: Model[] = [
  { model_name: "some-model", metadata: { model_type: "llm", icon: "Bot" } },
];

const noop = jest.fn();

describe("ModelSelection live-discovery empty state", () => {
  it("shows the configure-credentials hint for an unconfigured live-discovery provider", () => {
    render(
      <ModelSelection
        modelType="all"
        availableModels={[]}
        onModelToggle={noop}
        providerName="IBM WatsonX"
        liveDiscovery
        isConfigured={false}
      />,
    );

    expect(
      screen.getByTestId("live-discovery-empty-state"),
    ).toBeInTheDocument();
  });

  it("does not show the hint once the provider is configured", () => {
    render(
      <ModelSelection
        modelType="all"
        availableModels={[]}
        onModelToggle={noop}
        providerName="IBM WatsonX"
        liveDiscovery
        isConfigured
      />,
    );

    expect(
      screen.queryByTestId("live-discovery-empty-state"),
    ).not.toBeInTheDocument();
  });

  it("does not show the hint when models are available", () => {
    render(
      <ModelSelection
        modelType="all"
        availableModels={someModels}
        onModelToggle={noop}
        providerName="IBM WatsonX"
        liveDiscovery
        isConfigured={false}
      />,
    );

    expect(
      screen.queryByTestId("live-discovery-empty-state"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("some-model")).toBeInTheDocument();
  });

  it("keeps Ollama's specialized empty state instead of the generic hint", () => {
    render(
      <ModelSelection
        modelType="all"
        availableModels={[]}
        onModelToggle={noop}
        providerName="Ollama"
        liveDiscovery
        isConfigured={false}
      />,
    );

    expect(
      screen.queryByTestId("live-discovery-empty-state"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Check Ollama Library")).toBeInTheDocument();
  });

  it("renders nothing special for static-catalog providers", () => {
    render(
      <ModelSelection
        modelType="all"
        availableModels={[]}
        onModelToggle={noop}
        providerName="OpenAI"
        liveDiscovery={false}
        isConfigured={false}
      />,
    );

    expect(
      screen.queryByTestId("live-discovery-empty-state"),
    ).not.toBeInTheDocument();
  });
});
