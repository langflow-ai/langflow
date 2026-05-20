import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ProviderAccount } from "../types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);
jest.mock("@/components/ui/loading", () =>
  jest.fn(() => <span data-testid="loading-spinner" />),
);

import ProvidersTable from "../components/providers-table";

const makeProvider = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "prov-1",
  name: "Production WxO",
  provider_key: "watsonx-orchestrate",
  provider_data: { url: "https://api.example.com" },
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-05-10T00:00:00Z",
  ...overrides,
});

const noop = jest.fn();

function renderCards(
  providers: ProviderAccount[] = [makeProvider()],
  overrides: Partial<Parameters<typeof ProvidersTable>[0]> = {},
) {
  return render(
    <ProvidersTable
      providers={providers}
      onConfigureProvider={noop}
      onDeleteProvider={noop}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("Card rendering", () => {
  it("renders provider card with name, endpoint, provider label, and count", () => {
    renderCards([makeProvider()], {
      deploymentTotalsByProvider: { "prov-1": 8 },
    });

    expect(screen.getByTestId("provider-row-prov-1")).toBeInTheDocument();
    expect(screen.getByText("Production WxO")).toBeInTheDocument();
    expect(screen.getByText("watsonx Orchestrate")).toBeInTheDocument();
    expect(screen.getByText("https://api.example.com")).toBeInTheDocument();
    expect(screen.getByText("Deployments")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  it("renders multiple provider cards", () => {
    renderCards([
      makeProvider({ id: "prov-1", name: "Prod" }),
      makeProvider({ id: "prov-2", name: "Staging" }),
    ]);
    expect(screen.getByTestId("provider-row-prov-1")).toBeInTheDocument();
    expect(screen.getByTestId("provider-row-prov-2")).toBeInTheDocument();
  });

  it("shows dash when updated and created dates are null", () => {
    renderCards([makeProvider({ created_at: null, updated_at: null })]);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows zero deployments when totals are missing", () => {
    renderCards();
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});

describe("Actions", () => {
  it("calls onConfigureProvider when Configure is clicked", async () => {
    const user = userEvent.setup();
    const onConfigure = jest.fn();
    const provider = makeProvider();

    renderCards([provider], { onConfigureProvider: onConfigure });

    await user.click(screen.getByTestId("configure-provider-prov-1"));
    expect(onConfigure).toHaveBeenCalledWith(provider);
  });

  it("calls onDeleteProvider when Delete is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const provider = makeProvider();

    renderCards([provider], { onDeleteProvider: onDelete });

    await user.click(screen.getByTestId("delete-provider-prov-1"));
    expect(onDelete).toHaveBeenCalledWith(provider);
  });
});

describe("Deleting state", () => {
  it("shows loading spinner when deleting", () => {
    renderCards([makeProvider()], { deletingId: "prov-1" });
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
  });

  it("applies opacity to deleting card", () => {
    renderCards([makeProvider()], { deletingId: "prov-1" });
    const card = screen.getByTestId("provider-row-prov-1");
    expect(card.className).toContain("opacity-50");
  });

  it("does not affect other cards", () => {
    renderCards(
      [
        makeProvider({ id: "prov-1" }),
        makeProvider({ id: "prov-2", name: "Other" }),
      ],
      { deletingId: "prov-1" },
    );
    const otherCard = screen.getByTestId("provider-row-prov-2");
    expect(otherCard.className).not.toContain("opacity-50");
  });
});
