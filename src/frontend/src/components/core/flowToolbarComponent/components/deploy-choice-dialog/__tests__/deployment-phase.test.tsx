import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dialog } from "@/components/ui/dialog";
import type {
  Deployment,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import { axe } from "@/utils/a11y-test";
import DeploymentPhaseContent from "../deployment-phase";

const makeProvider = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "p1",
  name: "WxO Prod",
  provider_key: "watsonx-orchestrate",
  provider_data: { url: "https://wxo.example.com" },
  created_at: null,
  updated_at: null,
  ...overrides,
});

const makeDeployment = (
  id: string,
  name: string,
  overrides: Partial<Deployment> = {},
): Deployment => ({
  id,
  provider_id: "prov-1",
  description: null,
  type: "agent",
  created_at: "2025-01-01",
  updated_at: "2025-01-01",
  provider_data: { display_name: name, name: "x" },
  resource_key: "x",
  attached_count: 1,
  ...overrides,
});

const defaultProps = {
  selectedProvider: makeProvider(),
  deployments: [makeDeployment("d1", "My Bot")],
  selectedDeployment: "",
  onSelectDeployment: jest.fn(),
  isLoading: false,
  isBusy: false,
  showBack: false,
  onBack: jest.fn(),
  onContinue: jest.fn(),
  onCancel: jest.fn(),
};

function renderPhase(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(
    <Dialog open>
      <DeploymentPhaseContent {...props} />
    </Dialog>,
  );
}

describe("DeploymentPhaseContent", () => {
  it("renders the dialog title and description", () => {
    renderPhase();

    expect(screen.getByText("Select Deployment")).toBeInTheDocument();
    expect(
      screen.getByText("Deployments on WxO Prod for this flow."),
    ).toBeInTheDocument();
  });

  it("renders each deployment plus the create-new option as radio items", () => {
    renderPhase({
      deployments: [
        makeDeployment("d1", "My Bot"),
        makeDeployment("d2", "Other Bot"),
      ],
    });

    expect(screen.getByRole("radio", { name: /My Bot/ })).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /Other Bot/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /Create new deployment/ }),
    ).toBeInTheDocument();
  });

  it("translates the deployment type label instead of showing a raw literal", () => {
    renderPhase({ deployments: [makeDeployment("d1", "My Bot")] });

    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.queryByText(/^agent$/)).not.toBeInTheDocument();
  });

  it("falls back to the raw type value for an unrecognized deployment type", () => {
    renderPhase({
      deployments: [
        makeDeployment("d1", "My Bot", {
          type: "custom-type" as Deployment["type"],
        }),
      ],
    });

    expect(screen.getByText("custom-type")).toBeInTheDocument();
  });

  it("calls onSelectDeployment when a deployment is chosen", async () => {
    const user = userEvent.setup();
    const onSelectDeployment = jest.fn();
    renderPhase({ onSelectDeployment });

    await user.click(screen.getByRole("radio", { name: /My Bot/ }));

    expect(onSelectDeployment).toHaveBeenCalledWith("d1");
  });

  it("calls onContinue/onCancel/onBack", async () => {
    const user = userEvent.setup();
    const onContinue = jest.fn();
    const onCancel = jest.fn();
    const onBack = jest.fn();
    renderPhase({ showBack: true, onContinue, onCancel, onBack });

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(onContinue).toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalled();
    expect(onBack).toHaveBeenCalled();
  });
});

describe("Accessibility", () => {
  it("should_have_no_axe_violations in the loaded state", async () => {
    const { container } = renderPhase();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations in the loading state", async () => {
    const { container } = renderPhase({ isLoading: true, deployments: [] });

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: the loading spinner previously gave zero indication
  // to screen reader users that anything was happening — no role="status",
  // no aria-live, nothing. A sighted user sees a spinner; an AT user got
  // silence between the dialog title and the eventual radio list appearing.
  it("announces the loading state to assistive tech via role=status", () => {
    renderPhase({ isLoading: true, deployments: [] });

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading deployments...",
    );
  });

  it("does not render the loading status once deployments have loaded", () => {
    renderPhase({ isLoading: false });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
