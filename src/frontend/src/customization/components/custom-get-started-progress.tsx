import { GetStartedProgress } from "@/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/get-started-progress";
import { Users } from "@/types/api";

export function CustomGetStartedProgress({
  userData,
  isGithubStarred,
  isDiscordJoined,
  handleDismissDialog,
}: {
  userData: Users;
  isGithubStarred: boolean;
  isDiscordJoined: boolean;
  handleDismissDialog: () => void;
}) {
  return (
    <GetStartedProgress
      userData={userData}
      isGithubStarred={isGithubStarred}
      isDiscordJoined={isDiscordJoined}
      handleDismissDialog={handleDismissDialog}
    />
  );
}

export default CustomGetStartedProgress;
