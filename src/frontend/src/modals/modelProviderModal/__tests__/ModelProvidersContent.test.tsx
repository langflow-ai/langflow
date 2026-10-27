import { render, screen } from "@testing-library/react";
import ModelProvidersContent from "../components/ModelProvidersContent";

const mockProvider = {
  provider: "TypeSafe",
  models: [],
  is_configured: true,
  live_discovery: true,
  discovery_error: "Discovery unavailable",
};
jest.mock("../hooks/useProviderConfiguration", () => ({
  useProviderConfiguration: () => ({ syncedSelectedProvider: mockProvider }),
}));
jest.mock("../components/ProviderList", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("../components/ProviderConfigurationForm", () => ({
  __esModule: true,
  default: () => <button>Save credentials</button>,
}));
jest.mock("../components/ModelSelection", () => ({
  __esModule: true,
  default: () => null,
  hasProviderOwnedEmptyState: () => false,
}));

it("shows discovery failure alongside editable credentials and clears it after recovery", () => {
  const { rerender } = render(<ModelProvidersContent modelType="decision" />);
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Decision models could not be loaded",
  );
  expect(
    screen.getByRole("button", { name: "Save credentials" }),
  ).toBeEnabled();
  mockProvider.discovery_error = "";
  rerender(<ModelProvidersContent modelType="decision" />);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
