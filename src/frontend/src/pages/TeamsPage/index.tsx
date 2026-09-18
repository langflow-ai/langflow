import { TeamManagement } from "./components/team-management";

export default function TeamsPage({
  adminMode = false,
}: {
  adminMode?: boolean;
}) {
  return <TeamManagement adminMode={adminMode} />;
}
