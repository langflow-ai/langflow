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
  url: "https://api.example.com",
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-05-10T00:00:00Z",
  ...overrides,
});

const noop = jest.fn();

function renderTable(
  providers: ProviderAccount[] = [makeProvider()],
  overrides: Partial<Parameters<typeof ProvidersTable>[0]> = {},
) {
  return render(
    <ProvidersTable
      providers={providers}
      onDeleteProvider={noop}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Row rendering
// ---------------------------------------------------------------------------

describe("Row rendering", () => {
  it("renders a provider row with name, URL, and provider key", () => {
    renderTable();
    expect(screen.getByTestId("provider-row-prov-1")).toBeInTheDocument();
    expect(screen.getByText("Production WxO")).toBeInTheDocument();
    expect(screen.getByText("https://api.example.com")).toBeInTheDocument();
    expect(screen.getByText("watsonx-orchestrate")).toBeInTheDocument();
  });

  it("renders multiple provider rows", () => {
    renderTable([
      makeProvider({ id: "prov-1", name: "Prod" }),
      makeProvider({ id: "prov-2", name: "Staging" }),
    ]);
    expect(screen.getByTestId("provider-row-prov-1")).toBeInTheDocument();
    expect(screen.getByTestId("provider-row-prov-2")).toBeInTheDocument();
  });

  it("shows dash when created_at is null", () => {
    renderTable([makeProvider({ created_at: null })]);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Column headers
// ---------------------------------------------------------------------------

describe("Column headers", () => {
  it("renders all expected column headers", () => {
    renderTable();
    for (const header of ["Name", "URL", "Provider Key", "Created"]) {
      expect(screen.getByText(header)).toBeInTheDocument();
    }
  });
});

// ---------------------------------------------------------------------------
// Delete action
// ---------------------------------------------------------------------------

describe("Delete action", () => {
  it("calls onDeleteProvider when Delete is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const provider = makeProvider();
    renderTable([provider], { onDeleteProvider: onDelete });

    await user.click(screen.getByTestId("actions-provider-prov-1"));
    await user.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith(provider);
  });

  it("has correct aria-label on actions button", () => {
    renderTable();
    expect(screen.getByTestId("actions-provider-prov-1")).toHaveAttribute(
      "aria-label",
      "Actions for Production WxO",
    );
  });
});

// ---------------------------------------------------------------------------
// Deleting state
// ---------------------------------------------------------------------------

describe("Deleting state", () => {
  it("shows loading spinner when deleting", () => {
    renderTable([makeProvider()], { deletingId: "prov-1" });
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
    expect(
      screen.queryByTestId("actions-provider-prov-1"),
    ).not.toBeInTheDocument();
  });

  it("applies opacity to the deleting row", () => {
    renderTable([makeProvider()], { deletingId: "prov-1" });
    const row = screen.getByTestId("provider-row-prov-1");
    expect(row.className).toContain("opacity-50");
  });

  it("does not affect other rows", () => {
    renderTable(
      [
        makeProvider({ id: "prov-1" }),
        makeProvider({ id: "prov-2", name: "Other" }),
      ],
      { deletingId: "prov-1" },
    );
    const otherRow = screen.getByTestId("provider-row-prov-2");
    expect(otherRow.className).not.toContain("opacity-50");
  });
});
