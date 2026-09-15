import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ShareSummary } from "@/types/authz";
import { axe } from "@/utils/a11y-test";
import { ResourceShareDialog } from "../resource-share-dialog";

const mockCreateShare = jest.fn();
const mockUpdateShare = jest.fn();
const mockDeleteShare = jest.fn();
const mockUseGetShareSummary = jest.fn();

const emptySummary: ShareSummary = {
  resource_type: "flow",
  resource_id: "flow-1",
  display_name: "Quarterly agent",
  subject_user_id: "owner-1",
  caller_is_owner: true,
  can_manage_shares: true,
  direct_grants: [],
  effective_access: { actions: [], sources: [] },
  inherited_from_project: false,
  legacy_public_access: false,
  administrative_grant_present: false,
  has_more: false,
  next_offset: null,
};

let mockSummaryData: ShareSummary = emptySummary;

jest.mock("@/controllers/API/queries/authorization", () => ({
  useGetAuthorizationCapabilities: () => ({
    data: {
      enforcement_active: true,
      service_ready: true,
      user_team_sharing_supported: true,
      share_modes: ["execute", "write"],
    },
    isLoading: false,
    isError: false,
  }),
  useSearchAuthorizationRecipients: () => ({
    data: {
      items: [{ id: "user-2", kind: "user", display_name: "Second User" }],
    },
    isFetching: false,
  }),
}));

jest.mock("@/controllers/API/queries/shares", () => ({
  useGetShareSummary: (...args: unknown[]) => mockUseGetShareSummary(...args),
  useCreateShare: () => ({ mutate: mockCreateShare, isPending: false }),
  useUpdateShare: () => ({ mutate: mockUpdateShare, isPending: false }),
  useDeleteShare: () => ({ mutate: mockDeleteShare, isPending: false }),
}));

const renderDialog = () =>
  render(
    <ResourceShareDialog
      open
      onOpenChange={jest.fn()}
      resourceType="flow"
      resourceId="flow-1"
      resourceName="Quarterly agent"
    />,
  );

describe("ResourceShareDialog", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSummaryData = emptySummary;
    mockUseGetShareSummary.mockImplementation(() => ({
      data: mockSummaryData,
      isLoading: false,
      isFetching: false,
      isError: false,
    }));
  });

  it("offers exactly the two supported grant modes and creates a direct user grant", () => {
    renderDialog();

    expect(screen.getAllByText("Not editable — Can use")).toHaveLength(1);
    expect(screen.getAllByText("Editable — Can edit")).toHaveLength(1);
    expect(screen.queryByText(/public link/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Second User" }));
    fireEvent.click(screen.getByRole("button", { name: "Share" }));

    expect(mockCreateShare).toHaveBeenCalledWith({
      resourceType: "flow",
      resourceId: "flow-1",
      recipientType: "user",
      recipientId: "user-2",
      permission: "execute",
    });
  });

  it("has no detectable axe violations in its ready state", async () => {
    renderDialog();

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("removes grant controls when a summary refetch fails with cached data", () => {
    const { rerender } = renderDialog();
    expect(screen.getByRole("button", { name: "Share" })).toBeInTheDocument();
    mockUseGetShareSummary.mockReturnValue({
      data: emptySummary,
      isLoading: false,
      isFetching: false,
      isError: true,
    });
    rerender(
      <ResourceShareDialog
        open
        onOpenChange={jest.fn()}
        resourceType="flow"
        resourceId="flow-1"
      />,
    );
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
    expect(mockCreateShare).not.toHaveBeenCalled();
  });

  it("preserves API-created grants until an explicit supported conversion", () => {
    mockSummaryData = {
      ...emptySummary,
      direct_grants: [
        {
          id: "read-grant",
          resource_type: "flow",
          resource_id: "flow-1",
          scope: "user",
          target_id: "read-recipient",
          target_name: "Read Recipient",
          permission_level: "read",
          revision: 1,
          created_at: "2026-09-03T00:00:00Z",
          updated_at: "2026-09-03T00:00:00Z",
        },
        {
          id: "admin-grant",
          resource_type: "flow",
          resource_id: "flow-1",
          scope: "team",
          target_id: "admin-team",
          target_name: "Admin Team",
          permission_level: "admin",
          revision: 2,
          created_at: "2026-09-03T00:00:00Z",
          updated_at: "2026-09-03T00:00:00Z",
        },
      ],
    };

    renderDialog();

    const readGrant = screen.getByTestId("share-grant-read-grant");
    expect(
      within(readGrant).getByText("Read only — API-managed"),
    ).toBeInTheDocument();
    const convertReadToUse = within(readGrant).getByRole("radio", {
      name: "Not editable — Can use",
    });
    expect(convertReadToUse).not.toBeChecked();

    const adminGrant = screen.getByTestId("share-grant-admin-grant");
    expect(
      within(adminGrant).getByText("Administrative — API-managed"),
    ).toBeInTheDocument();
    const convertAdminToEdit = within(adminGrant).getByRole("radio", {
      name: "Editable — Can edit",
    });
    expect(convertAdminToEdit).not.toBeChecked();
    expect(mockUpdateShare).not.toHaveBeenCalled();

    fireEvent.click(convertReadToUse);
    expect(mockUpdateShare).toHaveBeenNthCalledWith(1, {
      shareId: "read-grant",
      revision: 1,
      resourceType: "flow",
      resourceId: "flow-1",
      permission: "execute",
    });

    fireEvent.click(convertAdminToEdit);
    expect(mockUpdateShare).toHaveBeenNthCalledWith(2, {
      shareId: "admin-grant",
      revision: 2,
      resourceType: "flow",
      resourceId: "flow-1",
      permission: "write",
    });
  });

  it("requests the next bounded page of direct grants", () => {
    mockSummaryData = { ...emptySummary, has_more: true, next_offset: 50 };
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(mockUseGetShareSummary).toHaveBeenLastCalledWith(
      {
        resourceType: "flow",
        resourceId: "flow-1",
        limit: 50,
        offset: 50,
      },
      { enabled: true },
    );
  });

  it("clears a pending grant when the dialog is closed and reopened", () => {
    const onOpenChange = jest.fn();
    const view = render(
      <ResourceShareDialog
        open
        onOpenChange={onOpenChange}
        resourceType="flow"
        resourceId="flow-1"
        resourceName="Quarterly agent"
      />,
    );

    fireEvent.change(
      screen.getByRole("textbox", { name: "Search recipients" }),
      {
        target: { value: "Second" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Second User" }));
    fireEvent.click(screen.getByRole("radio", { name: /^Editable/ }));
    expect(screen.getByRole("button", { name: "Share" })).toBeEnabled();

    view.rerender(
      <ResourceShareDialog
        open={false}
        onOpenChange={onOpenChange}
        resourceType="flow"
        resourceId="flow-1"
        resourceName="Quarterly agent"
      />,
    );
    view.rerender(
      <ResourceShareDialog
        open
        onOpenChange={onOpenChange}
        resourceType="flow"
        resourceId="flow-1"
        resourceName="Quarterly agent"
      />,
    );

    expect(
      screen.getByRole("textbox", { name: "Search recipients" }),
    ).toHaveValue("");
    expect(screen.getByRole("radio", { name: /^Not editable/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Share" })).toBeDisabled();
  });
});
