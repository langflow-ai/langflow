/**
 * Component tests for AssistantNoModelsState.
 *
 * The "Configure Model Providers" CTA must open the inline
 * ModelProviderModal — matching FlowBuilderWelcome and ModelSelector — instead
 * of navigating to the Settings page, so the user stays inside the flow
 * builder context.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssistantNoModelsState } from "../assistant-no-models-state";

jest.mock("@/assets/langflow_assistant.svg", () => "langflow-icon.svg");

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} />;
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: "3rdParty", init: jest.fn() },
}));

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="mock-model-provider-modal" /> : null,
}));

describe("AssistantNoModelsState", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_open_provider_modal_when_configure_clicked", async () => {
    render(<AssistantNoModelsState />);

    expect(
      screen.queryByTestId("mock-model-provider-modal"),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByTestId("assistant-no-models-configure-providers"),
    );

    expect(screen.getByTestId("mock-model-provider-modal")).toBeInTheDocument();
  });

  it("should_not_navigate_to_settings_when_configure_clicked", async () => {
    render(<AssistantNoModelsState />);

    await userEvent.click(
      screen.getByTestId("assistant-no-models-configure-providers"),
    );

    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
