import { GetStartedProgress } from "@/components/core/folderSidebarComponent/components/sideBarFolderButtons/components/get-started-progress";
import type { Users } from "@/types/api";

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
  // The divider belongs to the checklist, so an override that renders nothing
  // leaves no stray rule above the project list.
  return (
    <>
      <GetStartedProgress
        userData={userData}
        isGithubStarred={isGithubStarred}
        isDiscordJoined={isDiscordJoined}
        handleDismissDialog={handleDismissDialog}
      />

      <div className="-mx-4 mt-1 w-[280px]">
        <hr className="border-t-1 w-full" />
      </div>
    </>
  );
}

export default CustomGetStartedProgress;
