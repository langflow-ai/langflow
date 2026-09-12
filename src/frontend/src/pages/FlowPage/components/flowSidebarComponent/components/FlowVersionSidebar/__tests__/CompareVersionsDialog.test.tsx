import { fireEvent, render, screen } from "@testing-library/react";
import type { FlowVersionDiff } from "@/types/flow/version";
import CompareVersionsDialog from "../components/CompareVersionsDialog";

const mockUseGetFlowVersionDiff = jest.fn();

jest.mock("@/controllers/API/queries/flow-version", () => ({
  useGetFlowVersionDiff: (...args: unknown[]) =>
    mockUseGetFlowVersionDiff(...args),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

const emptySummary = {
  nodes_added: 0,
  nodes_removed: 0,
  nodes_modified: 0,
  nodes_unchanged: 0,
  edges_added: 0,
  edges_removed: 0,
  edges_unchanged: 0,
  fields_changed: 0,
  code_fields_changed: 0,
  secrets_changed: 0,
};

function buildDiff(overrides: Partial<FlowVersionDiff> = {}): FlowVersionDiff {
  return {
    base: { kind: "version", version_tag: "v1" },
    target: { kind: "draft" },
    summary: { ...emptySummary },
    nodes: { added: [], removed: [], modified: [] },
    edges: { added: [], removed: [] },
    identical: false,
    truncated: false,
    ...overrides,
  };
}

function renderDialog(
  state: { data?: FlowVersionDiff; isLoading?: boolean; isError?: boolean },
  props: Partial<React.ComponentProps<typeof CompareVersionsDialog>> = {},
) {
  mockUseGetFlowVersionDiff.mockReturnValue({
    data: state.data,
    isLoading: state.isLoading ?? false,
    isError: state.isError ?? false,
  });
  return render(
    <CompareVersionsDialog
      flowId="flow-1"
      baseVersionId="version-1"
      against="draft"
      onClose={jest.fn()}
      onSwap={jest.fn()}
      {...props}
    />,
  );
}

beforeEach(() => {
  mockUseGetFlowVersionDiff.mockReset();
});

describe("CompareVersionsDialog", () => {
  it("shows a loading state while the diff is in flight", () => {
    renderDialog({ isLoading: true });

    expect(screen.getByText("Comparing…")).toBeInTheDocument();
  });

  it("shows an error state when the diff fails", () => {
    renderDialog({ isError: true });

    expect(screen.getByText("Failed to load comparison")).toBeInTheDocument();
  });

  it("shows the empty state when the two sides are identical", () => {
    renderDialog({ data: buildDiff({ identical: true }) });

    expect(screen.getByText("No differences")).toBeInTheDocument();
  });

  it("renders added and removed components", () => {
    renderDialog({
      data: buildDiff({
        summary: { ...emptySummary, nodes_added: 1, nodes_removed: 1 },
        nodes: {
          added: [{ id: "n2", display_name: "Chat Output" }],
          removed: [{ id: "n3", display_name: "Prompt" }],
          modified: [],
        },
      }),
    });

    expect(screen.getByText("Chat Output")).toBeInTheDocument();
    expect(screen.getByText("Prompt")).toBeInTheDocument();
  });

  it("renders before and after values for an ordinary field change", () => {
    renderDialog({
      data: buildDiff({
        summary: { ...emptySummary, nodes_modified: 1, fields_changed: 1 },
        nodes: {
          added: [],
          removed: [],
          modified: [
            {
              id: "n1",
              display_name: "OpenAI",
              field_changes: [
                {
                  name: "temperature",
                  status: "modified",
                  redacted: false,
                  before: 0.7,
                  after: 0.2,
                  before_truncated: false,
                  after_truncated: false,
                },
              ],
              code_changes: [],
              other_changed_keys: [],
            },
          ],
        },
      }),
    });

    expect(screen.getByText("0.7")).toBeInTheDocument();
    expect(screen.getByText("0.2")).toBeInTheDocument();
    expect(screen.queryByTestId("redacted-value-pill")).not.toBeInTheDocument();
  });

  it("hides both values behind a pill for a redacted field", () => {
    renderDialog({
      data: buildDiff({
        summary: { ...emptySummary, nodes_modified: 1, secrets_changed: 1 },
        nodes: {
          added: [],
          removed: [],
          modified: [
            {
              id: "n1",
              display_name: "OpenAI",
              field_changes: [
                {
                  name: "api_key",
                  status: "modified",
                  redacted: true,
                  before_truncated: false,
                  after_truncated: false,
                },
              ],
              code_changes: [],
              other_changed_keys: [],
            },
          ],
        },
      }),
    });

    expect(screen.getByTestId("redacted-value-pill")).toBeInTheDocument();
    expect(screen.getByText("Value hidden (secret)")).toBeInTheDocument();
    // A redacted change carries no before/after at all, so nothing renders a
    // value cell for it.
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("renders a code change with its line counts and diff body", () => {
    renderDialog({
      data: buildDiff({
        summary: { ...emptySummary, nodes_modified: 1, code_fields_changed: 1 },
        nodes: {
          added: [],
          removed: [],
          modified: [
            {
              id: "n1",
              display_name: "Custom",
              field_changes: [],
              code_changes: [
                {
                  field_name: "code",
                  added_lines: 2,
                  removed_lines: 1,
                  unified_diff: "@@ -1 +1,2 @@\n-old\n+new\n+extra",
                  truncated: false,
                  redacted: false,
                },
              ],
              other_changed_keys: [],
            },
          ],
        },
      }),
    });

    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.getByText("-1")).toBeInTheDocument();
    expect(screen.getByText("+new")).toBeInTheDocument();
    expect(screen.getByText("-old")).toBeInTheDocument();
  });

  it("invokes the swap handler when both sides are versions", () => {
    const onSwap = jest.fn();
    renderDialog({ data: buildDiff() }, { onSwap, against: "version-2" });

    fireEvent.click(screen.getByLabelText("Swap sides"));

    expect(onSwap).toHaveBeenCalledTimes(1);
  });

  it("disables swapping against the draft rather than leaving a dead button", () => {
    const onSwap = jest.fn();
    renderDialog({ data: buildDiff() }, { onSwap, against: "draft" });

    const swap = screen.getByLabelText("Swap sides");

    expect(swap).toBeDisabled();
    fireEvent.click(swap);
    expect(onSwap).not.toHaveBeenCalled();
  });

  it("requests the diff for the supplied base and target", () => {
    renderDialog({ data: buildDiff() }, { against: "version-2" });

    expect(mockUseGetFlowVersionDiff).toHaveBeenCalledWith({
      flowId: "flow-1",
      versionId: "version-1",
      against: "version-2",
    });
  });
});
