import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import type { APIClassType } from "@/types/api";
import { axe } from "@/utils/a11y-test";
import { mockUsePostTemplateValue } from "../../__tests__/a11y-mock-helpers";

// The shared Dropdown pulls in DropdownOptionsList -> NodeDialogComponent ->
// mcpComponent -> addMcpServerModal, which imports the ESM-only `nanoid`
// package. Stub it out — irrelevant to this a11y regression test and not
// otherwise transformed by Jest's CJS setup.
jest.mock("nanoid", () => ({ nanoid: () => "test-id" }));
jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () =>
  mockUsePostTemplateValue(),
);

import DropdownComponent from "..";

const renderWithQueryClient = (ui: ReactElement) => {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
};

const baseProps = {
  value: "",
  id: "dropdown-field",
  editNode: false,
  disabled: false,
  name: "dropdown",
  options: ["a", "b", "c"],
  handleOnNewValue: jest.fn(),
  handleNodeClass: jest.fn(),
  nodeClass: { template: {} } as unknown as APIClassType,
  nodeId: "node-1",
};

describe("DropdownComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderWithQueryClient(
      <>
        <span id="field-label">Model provider</span>
        <DropdownComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: this wrapper delegates rendering to the shared
  // @/components/core/dropdownComponent Dropdown via a prop spread — this
  // test proves ariaLabelledBy actually survives that pass-through end to
  // end, not just that the wrapper "has" the prop.
  it("uses the field's real label as the combobox trigger's accessible name", () => {
    renderWithQueryClient(
      <>
        <span id="field-label">Model provider</span>
        <DropdownComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("combobox", { name: "Model provider" }),
    ).toBeInTheDocument();
  });

  it("does not set aria-labelledby on the combobox trigger when absent", () => {
    renderWithQueryClient(<DropdownComponent {...baseProps} />);

    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-labelledby");
  });
});
