import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import OutputComponent from "..";

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => false,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      nodes: [{ id: "node-1", data: { type: "SomeComponent" } }],
      currentFlow: { id: "flow-1" },
    }),
}));

// Something in this file's import chain (Popover/Command + ShadTooltip)
// corrupts genericIconComponent's *named* ForwardedIconComponent export to
// undefined in this Jest setup — the same pre-existing test-infra issue
// found while working on TableNodeComponent. Mocking it sidesteps that so
// this widget's own trigger logic — the only thing this a11y fix touches
// — can actually be exercised.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: (props: { name?: string }) => (
    <svg data-testid={`icon-${props.name}`} />
  ),
  default: (props: { name?: string }) => (
    <svg data-testid={`icon-${props.name}`} />
  ),
}));

const baseProps = {
  selected: "",
  types: ["Message"],
  frozen: false,
  nodeId: "node-1",
  outputs: [
    { name: "output-a", display_name: "Output A", types: ["Message"] },
    { name: "output-b", display_name: "Output B", types: ["Message"] },
  ],
  idx: 0,
  name: "Output A",
  isToolMode: false,
  handleSelectOutput: jest.fn(),
  outputName: "output-a",
};

describe("OutputComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<OutputComponent {...baseProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: role="combobox" is author-name-only per the ARIA
  // spec (no fallback to content), so without an explicit aria-label this
  // trigger had no accessible name despite showing the output's name as
  // visible text.
  it("gives the output-selector trigger an accessible name", () => {
    render(<OutputComponent {...baseProps} />);

    expect(
      screen.getByRole("combobox", { name: "Output" }),
    ).toBeInTheDocument();
  });

  // Label only, not composed with the selected output's name — matching
  // the VoiceOver double-announce lesson from connectionComponent/
  // dropdownComponent: composing would announce the value twice.
  it("does not compose the selected output's name into the accessible name", () => {
    render(<OutputComponent {...baseProps} />);

    const trigger = screen.getByTestId("dropdown-output-output-a");
    expect(trigger).toHaveAttribute("aria-label", "Output");
    expect(trigger).not.toHaveAttribute("aria-label", "Output A");
  });
});
