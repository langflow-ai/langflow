import { act, render, screen } from "@testing-library/react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import TemplateContentComponent from ".";

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

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

describe("TemplateContentComponent catalog policy empty state", () => {
  beforeEach(() => {
    act(() => {
      useFlowsManagerStore.setState({ examples: [] });
      useUtilityStore.setState({ catalogGovernanceEnabled: false });
    });
  });

  it("explains when governance leaves no templates available", () => {
    act(() => {
      useUtilityStore.setState({ catalogGovernanceEnabled: true });
    });

    render(
      <TemplateContentComponent
        currentTab="all-templates"
        categories={[
          {
            title: "All templates",
            icon: "LayoutPanelTop",
            id: "all-templates",
          },
        ]}
        loading={false}
        onFlowCreating={jest.fn()}
      />,
    );

    expect(
      screen.getByText(
        "No templates are available under your organization's catalog policy.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear your search" }),
    ).not.toBeInTheDocument();
  });

  it("keeps a semantic clear-search action for ordinary empty results", () => {
    render(
      <TemplateContentComponent
        currentTab="all-templates"
        categories={[
          {
            title: "All templates",
            icon: "LayoutPanelTop",
            id: "all-templates",
          },
        ]}
        loading={false}
        onFlowCreating={jest.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Clear your search" }),
    ).toBeInTheDocument();
  });
});
