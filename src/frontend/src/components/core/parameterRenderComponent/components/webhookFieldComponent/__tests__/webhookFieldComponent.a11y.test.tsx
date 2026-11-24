import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import WebhookFieldComponent from "..";

jest.mock("@/customization/components/custom-secret-key-modal-button", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock(
  "@/controllers/API/queries/_builds/use-get-builds-polling-mutation",
  () => ({
    useGetBuildsMutation: () => ({ mutate: jest.fn() }),
  }),
);
jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

const baseProps = {
  value: "http://localhost/api/v1/webhook/test",
  id: "webhook-field",
  editNode: false,
  disabled: false,
  handleOnNewValue: jest.fn(),
};

describe("WebhookFieldComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Webhook endpoint</span>
        <WebhookFieldComponent
          {...baseProps}
          ariaLabelledBy="field-label"
          nodeInformationMetadata={{
            variableName: "endpoint",
            flowId: "flow-1",
            nodeType: "webhook",
            flowName: "test-flow",
            isAuth: false,
          }}
        />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: this component is a pure pass-through — it forwards
  // ariaLabelledBy via ...baseInputProps to whichever branch it delegates
  // to (CopyFieldAreaComponent or TextAreaComponent, both already wired).
  // These tests prove that pass-through actually survives end to end.
  it("forwards the field's real label to CopyFieldAreaComponent on the backend-url branch", () => {
    render(
      <>
        <span id="field-label">Webhook endpoint</span>
        <WebhookFieldComponent
          {...baseProps}
          ariaLabelledBy="field-label"
          nodeInformationMetadata={{
            variableName: "endpoint",
            flowId: "flow-1",
            nodeType: "webhook",
            flowName: "test-flow",
            isAuth: false,
          }}
        />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Webhook endpoint" }),
    ).toBeInTheDocument();
  });

  it("forwards the field's real label to TextAreaComponent on the curl branch", () => {
    render(
      <>
        <span id="field-label">Webhook curl command</span>
        <WebhookFieldComponent
          {...baseProps}
          ariaLabelledBy="field-label"
          nodeInformationMetadata={{
            variableName: "curl",
            flowId: "flow-1",
            nodeType: "webhook",
            flowName: "test-flow",
            isAuth: false,
          }}
        />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Webhook curl command" }),
    ).toBeInTheDocument();
  });
});
