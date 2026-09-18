import { fireEvent, render, screen } from "@testing-library/react";
import type { AuthorizationTeam, AuthorizationTeamMember } from "@/types/authz";
import { axe } from "@/utils/a11y-test";
import { TeamDetails } from "../team-details";

const mockUpdateTeam = jest.fn();
const mockRemoveMember = jest.fn();
const mockUseGetTeamMembers = jest.fn();
let currentTeam: AuthorizationTeam;
let currentMembers: AuthorizationTeamMember[];

jest.mock("@/controllers/API/queries/teams", () => ({
  useGetTeam: () => ({ data: currentTeam, isLoading: false, isError: false }),
  useGetTeamMembers: (...args: unknown[]) => mockUseGetTeamMembers(...args),
  useUpdateTeam: () => ({ mutate: mockUpdateTeam, isPending: false }),
  useAddTeamMember: () => ({ mutate: jest.fn(), isPending: false }),
  useUpdateTeamMemberRole: () => ({ mutate: jest.fn(), isPending: false }),
  useRemoveTeamMember: () => ({
    mutate: mockRemoveMember,
    isPending: false,
  }),
  useDeleteTeam: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock("../team-member-picker", () => ({
  TeamMemberPicker: () => <div data-testid="team-member-picker" />,
}));

const team = (
  overrides: Partial<AuthorizationTeam> = {},
): AuthorizationTeam => ({
  id: "team-1",
  team_name: "AI Engineering",
  adom_name: "ai-engineering",
  description: "Trusted collaborators",
  is_active: true,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  member_count: 3,
  active_member_count: 3,
  active_admin_count: 1,
  current_user_role: "admin",
  capabilities: {
    can_update: true,
    can_set_active: false,
    can_delete: false,
    can_add_user_member: true,
    can_add_privileged_member: true,
    can_change_roles: true,
    can_remove_user_member: true,
  },
  ...overrides,
});

const member = (
  id: string,
  role: AuthorizationTeamMember["role"],
  source = "manual",
): AuthorizationTeamMember => ({
  id: `membership-${id}`,
  team_id: "team-1",
  user_id: id,
  display_name: id,
  source,
  role,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
});

describe("TeamDetails", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseGetTeamMembers.mockImplementation(() => ({
      data: currentMembers,
      isLoading: false,
      isFetching: false,
      isError: false,
    }));
    currentTeam = team();
    currentMembers = [
      member("Admin User", "admin"),
      member("Ordinary User", "user"),
      member("Directory User", "user", "sso"),
    ];
  });

  it("lets a Team Admin edit ordinary metadata without changing the directory mapping", () => {
    render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    expect(screen.getByLabelText("Team name")).toBeEnabled();
    expect(screen.getByLabelText("Administrative domain")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Team name"), {
      target: { value: "AI Platform" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    expect(mockUpdateTeam).toHaveBeenCalledWith({
      teamId: "team-1",
      data: {
        team_name: "AI Platform",
        description: "Trusted collaborators",
      },
    });
  });

  it("does not offer a Maintainer privileged-member or source-managed removal", () => {
    currentTeam = team({
      current_user_role: "maintainer",
      capabilities: {
        ...team().capabilities,
        can_update: false,
        can_add_privileged_member: false,
        can_change_roles: false,
      },
    });

    render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    expect(
      screen.queryByRole("button", { name: "Remove Admin User" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Remove Directory User" }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove Ordinary User" }),
    );
    expect(mockRemoveMember).toHaveBeenCalledWith({
      teamId: "team-1",
      userId: "Ordinary User",
    });
  });

  it("lets a Team Admin change a directory-managed role without offering removal", () => {
    render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    const roleSelectors = screen.getAllByRole("combobox", { name: "Role" });
    expect(roleSelectors[2]).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Remove Directory User" }),
    ).toBeNull();
  });

  it("uses one lookahead row without rendering an empty next page", () => {
    currentMembers = Array.from({ length: 50 }, (_, index) =>
      member(`Member ${index + 1}`, "user"),
    );
    const view = render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    expect(mockUseGetTeamMembers).toHaveBeenLastCalledWith({
      teamId: "team-1",
      limit: 51,
      offset: 0,
    });
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

    currentMembers = [...currentMembers, member("Member 51", "user")];
    view.rerender(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
    expect(screen.queryByText("Member 51")).toBeNull();
  });

  it("starts from the first member page when the selected team changes", () => {
    currentMembers = Array.from({ length: 51 }, (_, index) =>
      member(`Member ${index + 1}`, "user"),
    );
    const view = render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(mockUseGetTeamMembers).toHaveBeenLastCalledWith({
      teamId: "team-1",
      limit: 51,
      offset: 50,
    });

    currentTeam = team({ id: "team-2", team_name: "Platform Engineering" });
    currentMembers = [member("New Team Admin", "admin")];
    view.rerender(<TeamDetails teamId="team-2" onDeleted={jest.fn()} />);

    expect(mockUseGetTeamMembers).toHaveBeenLastCalledWith({
      teamId: "team-2",
      limit: 51,
      offset: 0,
    });
  });

  it("has no detectable axe violations for the team management detail", async () => {
    render(<TeamDetails teamId="team-1" onDeleted={jest.fn()} />);

    expect(await axe(document.body)).toHaveNoViolations();
  });
});
