import { fireEvent, render, screen } from "@testing-library/react";
import type { AuthorizationRecipient, TeamRole } from "@/types/authz";
import { TeamCreateDialog } from "../team-create-dialog";

const mockCreateTeam = jest.fn();

jest.mock("@/controllers/API/queries/teams", () => ({
  useCreateTeam: () => ({ mutate: mockCreateTeam, isPending: false }),
}));

jest.mock("../team-member-picker", () => ({
  TeamMemberPicker: ({
    onAdd,
  }: {
    onAdd: (recipient: AuthorizationRecipient, role: TeamRole) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onAdd(
          { id: "admin-1", kind: "user", display_name: "Initial Admin" },
          "admin",
        )
      }
    >
      Add initial admin
    </button>
  ),
}));

describe("TeamCreateDialog", () => {
  beforeEach(() => jest.clearAllMocks());

  it("submits the initial active Admin in the same create request", () => {
    render(
      <TeamCreateDialog open onOpenChange={jest.fn()} onCreated={jest.fn()} />,
    );

    const createButton = screen.getByRole("button", { name: /create team/i });
    expect(createButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Team name"), {
      target: { value: "AI Engineering" },
    });
    fireEvent.change(screen.getByLabelText("Administrative domain"), {
      target: { value: "ai-engineering" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add initial admin" }));
    fireEvent.click(createButton);

    expect(mockCreateTeam).toHaveBeenCalledWith({
      team_name: "AI Engineering",
      adom_name: "ai-engineering",
      description: null,
      is_active: true,
      members: [{ user_id: "admin-1", role: "admin" }],
    });
  });
});
