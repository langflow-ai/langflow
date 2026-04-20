import { render, screen } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockData: {
  flow_versions: Array<{
    id: string;
    flow_id: string;
    flow_name: string | null;
    version_number: number;
    attached_at: string | null;
    provider_snapshot_id: string | null;
    provider_data: { app_ids?: string[]; tool_name?: string } | null;
  }>;
} | null = null;
let mockIsLoading = false;
let mockIsError = false;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-attachments",
  () => ({
    useGetDeploymentAttachments: () => ({
      data: mockData,
      isLoading: mockIsLoading,
      isError: mockIsError,
    }),
  }),
);

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

// Mock table components so we can render outside a real <table>
jest.mock("@/components/ui/table", () => ({
  TableRow: ({ children, ...props }: React.PropsWithChildren<object>) => (
    <tr {...props}>{children}</tr>
  ),
  TableCell: ({
    children,
    ...props
  }: React.PropsWithChildren<{ colSpan?: number }>) => (
    <td {...props}>{children}</td>
  ),
}));

import DeploymentExpandedRow from "../components/deployment-expanded-row";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderRow(deploymentId = "dep-1", colSpan = 6) {
  return render(
    <table>
      <tbody>
        <DeploymentExpandedRow deploymentId={deploymentId} colSpan={colSpan} />
      </tbody>
    </table>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockData = null;
  mockIsLoading = false;
  mockIsError = false;
});

describe("DeploymentExpandedRow", () => {
  it("shows a loading spinner when data is loading", () => {
    mockIsLoading = true;
    renderRow();
    expect(screen.getByText("Loading attached flows...")).toBeInTheDocument();
    expect(screen.getByTestId("loading-icon")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", () => {
    mockIsError = true;
    renderRow();
    expect(
      screen.getByText("Failed to load attached flows"),
    ).toBeInTheDocument();
  });

  it('shows "No flows attached" when flow_versions is empty', () => {
    mockData = { flow_versions: [] };
    renderRow();
    expect(screen.getByText("No flows attached")).toBeInTheDocument();
  });

  it('shows "No flows attached" when data is null (flow_versions defaults to [])', () => {
    mockData = null;
    renderRow();
    expect(screen.getByText("No flows attached")).toBeInTheDocument();
  });

  it("renders a badge for each attached flow with version numbers", () => {
    mockData = {
      flow_versions: [
        {
          id: "fv-1",
          flow_id: "f-1",
          flow_name: "Flow A",
          version_number: 1,
          attached_at: null,
          provider_snapshot_id: null,
          provider_data: null,
        },
        {
          id: "fv-2",
          flow_id: "f-2",
          flow_name: "Flow B",
          version_number: 4,
          attached_at: null,
          provider_snapshot_id: null,
          provider_data: null,
        },
      ],
    };
    renderRow();
    expect(screen.getByText("Flow A")).toBeInTheDocument();
    expect(screen.getByText("Flow B")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v4")).toBeInTheDocument();
    expect(screen.getByText("Attached Flows")).toBeInTheDocument();
  });

  it('falls back to "Untitled" when flow_name is null', () => {
    mockData = {
      flow_versions: [
        {
          id: "fv-1",
          flow_id: "f-1",
          flow_name: null,
          version_number: 2,
          attached_at: null,
          provider_snapshot_id: null,
          provider_data: null,
        },
      ],
    };
    renderRow();
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });
});
