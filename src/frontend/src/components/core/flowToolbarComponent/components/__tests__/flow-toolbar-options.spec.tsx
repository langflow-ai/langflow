import { fireEvent, render, screen } from "@testing-library/react";

let mockToolbarStatus:
  | "loading"
  | "deployed"
  | "changes_not_deployed"
  | "not_deployed" = "deployed";

jest.mock("@/hooks/flows/use-flow-deployment-status", () => ({
  useFlowDeploymentStatus: () => ({
    toolbarStatus: mockToolbarStatus,
  }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ hasIO: true }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      currentFlow: { id: "flow-1", name: "Test Flow" },
    }),
}));

jest.mock("@/stores/historyPreviewStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ previewId: null }),
}));

jest.mock("../deploy-dropdown", () => ({
  __esModule: true,
  default: () => <div data-testid="publish-dropdown">Publish</div>,
}));

jest.mock("../playground-button", () => ({
  __esModule: true,
  default: () => <div data-testid="playground-button">Playground</div>,
}));

jest.mock("../flow-deploy-modal", () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) => (
    <div data-testid="flow-deploy-modal">{open ? "open" : "closed"}</div>
  ),
}));

import FlowToolbarOptions from "../flow-toolbar-options";

describe("FlowToolbarOptions", () => {
  it("renders deployed status badge", () => {
    mockToolbarStatus = "deployed";
    render(
      <FlowToolbarOptions openApiModal={false} setOpenApiModal={() => {}} />,
    );

    expect(screen.getByText("Deployed")).toBeTruthy();
  });

  it("opens deploy modal when deploy button is clicked", () => {
    mockToolbarStatus = "not_deployed";
    render(
      <FlowToolbarOptions openApiModal={false} setOpenApiModal={() => {}} />,
    );

    expect(screen.getByTestId("flow-deploy-modal").textContent).toBe("closed");
    fireEvent.click(screen.getByTestId("deploy-button"));
    expect(screen.getByTestId("flow-deploy-modal").textContent).toBe("open");
  });
});
