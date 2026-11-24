import { render, screen } from "@testing-library/react";
import type { APIClassType } from "@/types/api";
import { axe } from "@/utils/a11y-test";
import {
  mockUsePostTemplateValue,
  mockZustandStore,
} from "../../__tests__/a11y-mock-helpers";
import ConnectionComponent from "..";

jest.mock(
  "@/CustomNodes/GenericNode/components/ListSelectionComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);
jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () =>
  mockUsePostTemplateValue(),
);
jest.mock("@/stores/alertStore", () =>
  mockZustandStore({ setErrorData: jest.fn() }),
);

const baseProps = {
  value: "",
  id: "connection-field",
  editNode: false,
  disabled: false,
  name: "connection",
  handleOnNewValue: jest.fn(),
  handleNodeClass: jest.fn(),
  nodeClass: { template: {} } as unknown as APIClassType,
  nodeId: "node-1",
  options: [],
};

describe("ConnectionComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">API connection</span>
        <ConnectionComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: label only, not composed with the selected option's
  // name — role="combobox" gets special handling from screen readers, so
  // composing would double-announce the value (VoiceOver lesson from
  // dropdownComponent/modelInputComponent).
  it("uses the field's real label as the combobox trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">API connection</span>
        <ConnectionComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("combobox", { name: "API connection" }),
    ).toBeInTheDocument();
  });

  // Regression guard: the icon-only "connect" button previously had zero
  // accessible name at all, found while wiring this widget's field label.
  it("gives the icon-only connect button its own accessible name", () => {
    render(<ConnectionComponent {...baseProps} />);

    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });

  // Fallback case: no field label wired up. The combobox trigger must not
  // carry a stray aria-labelledby pointing at nothing, and the connect
  // button's own label must be unaffected either way.
  it("does not set aria-labelledby on the combobox trigger when absent", () => {
    render(<ConnectionComponent {...baseProps} />);

    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-labelledby");
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });
});
