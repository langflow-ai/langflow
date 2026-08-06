import { render, screen } from "@testing-library/react";
import { CustomLinkComponent } from "../custom-linkComponent";

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

const baseProps = {
  value: "example.com",
  disabled: false,
  id: "link-field",
  editNode: false,
  handleOnNewValue: jest.fn(),
};

describe("CustomLinkComponent", () => {
  // Regression guard: this is the actual wrapper ParameterRenderComponent
  // renders for "link" type fields (LinkComponent itself is never rendered
  // directly by the app) — it was dropping ariaLabelledBy on the floor
  // instead of forwarding it, silently making the fix on LinkComponent
  // dead code in production despite LinkComponent's own tests passing.
  it("forwards ariaLabelledBy through to the underlying LinkComponent", () => {
    render(
      <>
        <span id="field-label">Documentation</span>
        <CustomLinkComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Documentation" }),
    ).toBeInTheDocument();
  });
});
