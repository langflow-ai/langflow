import { useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useUpdateUser } from "@/controllers/API/queries/auth";
import CustomGetStartedProgress from "@/customization/components/custom-get-started-progress";
import useAuthStore from "@/stores/authStore";
import { AddFolderButton } from "./add-folder-button";
import { UploadFolderButton } from "./upload-folder-button";

export const HeaderButtons = ({
  handleUploadFlowsToFolder,
  isUpdatingFolder,
  isPending,
  addNewFolder,
}: {
  handleUploadFlowsToFolder: () => void;
  isUpdatingFolder: boolean;
  isPending: boolean;
  addNewFolder: () => void;
}) => {
  const userData = useAuthStore((state) => state.userData);

  const [isDismissedDialog, setIsDismissedDialog] = useState(
    userData?.optins?.dialog_dismissed,
  );
  const [isGithubStarred, setIsGithubStarred] = useState(
    userData?.optins?.github_starred,
  );
  const [isDiscordJoined, setIsDiscordJoined] = useState(
    userData?.optins?.discord_clicked,
  );

  const { mutate: updateUser } = useUpdateUser();

  useEffect(() => {
    if (userData) {
      setIsDismissedDialog(userData.optins?.dialog_dismissed);
      setIsGithubStarred(userData.optins?.github_starred);
      setIsDiscordJoined(userData.optins?.discord_clicked);
    }
  }, [userData]);

  const handleDismissDialog = () => {
    setIsDismissedDialog(true);
    updateUser({
      user_id: userData?.id!,
      user: {
        optins: {
          ...userData?.optins,
          dialog_dismissed: true,
        },
      },
    });
  };

  return (
    <>
      {!isDismissedDialog && userData && (
        <>
          <CustomGetStartedProgress
            userData={userData!}
            isGithubStarred={isGithubStarred ?? false}
            isDiscordJoined={isDiscordJoined ?? false}
            handleDismissDialog={handleDismissDialog}
          />

          <div className="-mx-4 mt-1 w-[280px]">
            <hr className="border-t-1 w-full" />
          </div>
        </>
      )}

      <div className="flex shrink-0 items-center justify-between gap-2 pt-2">
        <SidebarTrigger className="lg:hidden">
          <IconComponent name="PanelLeftClose" className="h-4 w-4" />
        </SidebarTrigger>

        <div className="flex-1 text-sm font-medium">Projects</div>
        <div className="flex items-center gap-1">
          <UploadFolderButton
            onClick={handleUploadFlowsToFolder}
            disabled={isUpdatingFolder}
          />
          <AddFolderButton
            onClick={addNewFolder}
            disabled={isUpdatingFolder}
            loading={isPending}
          />
        </div>
      </div>
    </>
  );
};
