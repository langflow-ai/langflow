import { render, screen } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import FlowSettingsModal from "../index";

// NOTE ON SCOPE: jest.setup.js globally stubs @radix-ui/react-form down to
// bare children, so no <label>/<form> elements exist in this environment.
// Un-stubbing it is not an option — the real Form.Root renders a genuine
// <form>, which makes Radix's Switch mount its hidden form-control bubble in a
// ref callback that setStates on every commit, hanging the run under React 19
// + jsdom. Field labelling is therefore NOT auditable here and is covered at
// the page level by the IBM Playwright scans instead; the axe rules that
// depend on it are disabled below with that justification. Everything else
// about the modal shell — dialog semantics, naming, disabled/read-only
// states — is real.
const FORM_STUB_RULES = {
  // Both fire only because the global Radix Form stub deletes the <label>
  // elements that production actually renders.
  label: { enabled: false },
  "form-field-multiple-labels": { enabled: false },
};

const mockSaveFlow = jest.fn();
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setSuccessData: jest.fn() }),
}));

const mockFlowState = { currentFlow: undefined, setCurrentFlow: jest.fn() };
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) => selector(mockFlowState),
}));

// The store state object must be referentially stable: FlowSettingsComponent
// keys a `useEffect` on `flows`, and returning a fresh array each render loops
// that effect forever.
const mockFlowsManagerState = {
  autoSaving: true,
  flows: [{ name: "Another flow" }],
  setCurrentFlow: jest.fn(),
};
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector(mockFlowsManagerState),
}));

// The real hook fails closed while permissions load, which would render every
// control disabled and hide the editable state worth auditing.
let mockReadOnly = false;
jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => mockReadOnly,
}));

const flowData = {
  id: "flow-1",
  name: "Customer support agent",
  description: "Answers questions from the docs.",
  locked: false,
  data: null,
} as unknown as FlowType;

const renderModal = () =>
  render(<FlowSettingsModal open setOpen={jest.fn()} flowData={flowData} />);

describe("FlowSettingsModal accessibility", () => {
  beforeEach(() => {
    mockReadOnly = false;
  });

  // Rather than switching `button-name` off wholesale, these two assert the
  // exact known-violation set. Any NEW violation still fails the suite, and
  // fixing the lock switch will fail them too — which is the correct prompt to
  // delete the exemption.
  it("should_have_no_axe_violations_beyond_the_known_lock_switch_gap", async () => {
    renderModal();

    // BaseModal portals its content to document.body, outside the render
    // container.
    const results = await axe(document.body, { rules: FORM_STUB_RULES });

    expect(results.violations.map((violation) => violation.id)).toEqual([
      "button-name",
    ]);
    expect(results.violations[0].nodes[0].html).toContain("lock-flow-switch");
  });

  it("should_have_no_new_axe_violations_in_read_only_state", async () => {
    mockReadOnly = true;
    renderModal();

    const results = await axe(document.body, { rules: FORM_STUB_RULES });

    expect(results.violations.map((violation) => violation.id)).toEqual([
      "button-name",
    ]);
  });

  it("should_expose_dialog_role_with_accessible_name", () => {
    renderModal();

    expect(
      screen.getByRole("dialog", { name: "Flow Details" }),
    ).toBeInTheDocument();
    // BaseModal.Header is present, so the visually-hidden "Dialog" fallback
    // must not be injected.
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
  });

  it("should_render_the_editable_controls_when_writable", () => {
    renderModal();

    expect(screen.getByTestId("input-flow-name")).toBeEnabled();
    expect(screen.getByTestId("input-flow-description")).toBeEnabled();
    expect(screen.getByRole("switch")).toBeEnabled();
  });

  it("should_disable_the_form_controls_when_read_only", () => {
    mockReadOnly = true;
    renderModal();

    expect(screen.getByTestId("input-flow-name")).toBeDisabled();
    expect(screen.getByTestId("input-flow-description")).toBeDisabled();
    expect(screen.getByRole("switch")).toBeDisabled();
    // A disabled control still has to explain why it cannot be used.
    expect(screen.getByTestId("save-flow-settings")).toHaveAttribute("title");
  });

  // FINDING (documented, not fixed): the "Lock Flow" Form.Label sits inside the
  // `description` Form.Field, so even with the real Radix Form it associates
  // with the description textarea rather than the Switch. The Switch itself
  // carries no aria-label / aria-labelledby, so it is announced with no name
  // (WCAG 4.1.2). This assertion holds regardless of the Form stub, because
  // the Switch is never inside a Form.Control.
  it("should_leave_the_lock_switch_without_an_accessible_name", () => {
    renderModal();

    expect(screen.getByRole("switch")).toHaveAccessibleName("");
  });

  it("should_expose_the_cancel_and_save_actions_as_buttons", () => {
    renderModal();

    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });
});
