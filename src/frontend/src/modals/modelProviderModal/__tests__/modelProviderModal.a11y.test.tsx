import { render, screen } from "@testing-library/react";
import ModelProviderModal from "../index";

jest.mock("../components/ModelProvidersContent", () => ({
  __esModule: true,
  default: () => <div data-testid="model-providers-content" />,
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({ refreshAllModelInputs: jest.fn() }),
}));

describe("ModelProviderModal accessibility", () => {
  it("should_give_the_dialog_an_accessible_name", () => {
    render(<ModelProviderModal open onClose={jest.fn()} modelType="all" />);

    // The heading was a plain styled div, so the dialog fell back to the
    // injected "Dialog" placeholder title.
    expect(
      screen.getByRole("dialog", { name: "Model providers" }),
    ).toBeInTheDocument();
  });
});
