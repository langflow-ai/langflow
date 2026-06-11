import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ dataTestId }: { dataTestId?: string }) => (
    <span data-testid={dataTestId} />
  ),
}));

import CopyFieldAreaComponent from "../index";

const renderComponent = () =>
  render(
    <CopyFieldAreaComponent
      value="http://localhost/api/v1/webhook/test"
      handleOnNewValue={jest.fn()}
      id="webhook_url"
      editNode={false}
      disabled={false}
      nodeClass={undefined as never}
      handleNodeClass={jest.fn()}
      nodeId="node-1"
      name="webhook_url"
    />,
  );

describe("CopyFieldAreaComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderComponent();

    expect(await axe(container)).toHaveNoViolations();
  });

  // Known gap (a11y-action-plan 2.4): the copy action is a bare <div
  // onClick> wrapping a decorative icon - no button role, no accessible
  // name, no keyboard activation. Fails until the fix lands.
  it("should_expose_copy_action_as_named_button", () => {
    renderComponent();

    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });
});
