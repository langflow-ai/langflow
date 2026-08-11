import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import GetStartedComponent from ".";

jest.mock("@/modals/baseModal", () => ({
  __esModule: true,
  default: {
    Header: ({ children }: { children: ReactNode }) => <>{children}</>,
  },
}));

jest.mock("../TemplateGetStartedCardComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="starter-card" />,
}));

jest.mock("../../../../assets/temp-pat-1.png", () => "image");
jest.mock("../../../../assets/temp-pat-2.png", () => "image");
jest.mock("../../../../assets/temp-pat-3.png", () => "image");
jest.mock("../../../../assets/temp-pat-m-1.png", () => "image");
jest.mock("../../../../assets/temp-pat-m-2.png", () => "image");
jest.mock("../../../../assets/temp-pat-m-3.png", () => "image");

describe("GetStartedComponent catalog policy empty state", () => {
  beforeEach(() => {
    act(() => {
      useFlowsManagerStore.setState({ examples: [] });
      useUtilityStore.setState({ catalogGovernanceEnabled: false });
    });
  });

  it("explains when governance leaves no featured starter templates", () => {
    act(() => {
      useUtilityStore.setState({ catalogGovernanceEnabled: true });
    });

    render(<GetStartedComponent loading={false} onFlowCreating={jest.fn()} />);

    expect(
      screen.getByText(
        "No featured starter templates are available under your organization's catalog policy.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("starter-card")).not.toBeInTheDocument();
  });
});
