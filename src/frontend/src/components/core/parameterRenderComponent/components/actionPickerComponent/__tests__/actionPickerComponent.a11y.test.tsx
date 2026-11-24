import { render, screen } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import { axe } from "@/utils/a11y-test";
import {
  mockGenericIconComponent,
  mockZustandStore,
} from "../../__tests__/a11y-mock-helpers";
import ActionPickerComponent from "../index";

jest.mock("@/stores/alertStore", () =>
  mockZustandStore({ setErrorData: jest.fn(), setNoticeData: jest.fn() }),
);

jest.mock("@/stores/flowStore", () =>
  mockZustandStore({ edges: [] as unknown[] }),
);

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const baseProps = {
  value: ["Approve", "Escalate"],
  handleOnNewValue: jest.fn(),
  nodeId: "node-1",
  id: "actionpicker_test",
} as unknown as ComponentProps<typeof ActionPickerComponent>;

describe("ActionPickerComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Actions</span>
        <ActionPickerComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: unlike a single-control widget, each button here
  // already carries its own specific name (e.g. "Rename search") — a group
  // label gives the field's context without doubling up on any control's
  // own name.
  it("uses the field's real label as the group's accessible name", () => {
    render(
      <>
        <span id="field-label">Actions</span>
        <ActionPickerComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(screen.getByRole("group", { name: "Actions" })).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<ActionPickerComponent {...baseProps} />);

    expect(screen.getByRole("group")).not.toHaveAttribute("aria-labelledby");
  });
});
