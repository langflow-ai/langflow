import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { DISCORD_URL, GITHUB_URL } from "@/constants/constants";
import { useGetUserData, useUpdateUser } from "@/controllers/API/queries/auth";
import ModalsComponent from "@/pages/MainPage/components/modalsComponent";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { Users } from "@/types/api";
import { cn } from "@/utils/utils";
import { type FC, useEffect, useMemo, useState } from "react";
import { FaDiscord, FaGithub } from "react-icons/fa";

export const GetStartedProgress: FC<{
  userData: Users;
  isGithubStarred: boolean;
  isDiscordJoined: boolean;
  handleDismissDialog: () => void;
}> = ({ userData, isGithubStarred, isDiscordJoined, handleDismissDialog }) => {
  const [isGithubStarredChild, setIsGithubStarredChild] =
    useState(isGithubStarred);
  const [isDiscordJoinedChild, setIsDiscordJoinedChild] =
    useState(isDiscordJoined);
  const [newProjectModal, setNewProjectModal] = useState(false);

  const flows = useFlowsManagerStore((state) => state.flows);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: updateUser } = useUpdateUser();

  useEffect(() => {
    if (!userData) {
      mutateLoggedUser(null);
    }
  }, [userData, mutateLoggedUser]);

  const hasFlows = flows && flows?.length > 0;

  const percentageGetStarted = useMemo(() => {
    const stepValue = 33;
    let totalPercentage = 0;

    if (userData?.optins?.github_starred) {
      totalPercentage += stepValue;
    }

    if (userData?.optins?.discord_clicked) {
      totalPercentage += stepValue;
    }

    if (hasFlows) {
      totalPercentage += stepValue;
    }

    if (totalPercentage === 99) {
      return 100;
    }

    return Math.min(totalPercentage, 100);
  }, [userData?.optins, hasFlows]);

  const handleUserTrack = (key: string) => {
    const optins = userData?.optins ?? {};
    optins[key] = true;

    updateUser(
      {
        user_id: userData?.id!,
        user: { optins },
      },
      {
        onSuccess: () => {
          mutateLoggedUser({});
          if (key === "github_starred") {
            setIsGithubStarredChild(true);
            window.open(GITHUB_URL, "_blank", "noopener,noreferrer");
          } else if (key === "discord_clicked") {
            setIsDiscordJoinedChild(true);
            window.open(DISCORD_URL, "_blank", "noopener,noreferrer");
          } else if (key === "dialog_dismissed") {
            handleDismissDialog();
          }
        },
      },
    );
  };

  return (
    <div className="mt-3 h-[10.8rem] w-full">
      <div className="mb-2 flex items-center justify-between">
        <span
          className="text-sm font-medium"
          data-testid="get_started_progress_title"
        >
          {percentageGetStarted >= 100 ? (
            <>
              <span>All Set</span> <span className="pl-1"> 🎉 </span>
            </>
          ) : (
            "Get started"
          )}
        </span>
        <button
          onClick={() => handleUserTrack("dialog_dismissed")}
          className="text-muted-foreground hover:text-foreground"
          data-testid="close_get_started_dialog"
        >
          <IconComponent name="X" className="h-4 w-4" />
        </button>
      </div>

      <div className="mb-1 mt-2 flex items-center justify-between gap-3">
        <div className="h-1 w-full rounded-full bg-muted">
          <div
            className="h-1 w-[33%] rounded-full bg-accent-pink-foreground"
            style={{ width: `${percentageGetStarted}%` }}
          />
        </div>
        <span
          className="text-sm text-muted-foreground"
          data-testid="get_started_progress_percentage"
        >
          {percentageGetStarted}%
        </span>
      </div>

      <div className="mt-2 space-y-1">
        <Button
          data-testid="github_starred_btn_get_started"
          unstyled
          className={cn(
            "w-full",
            isGithubStarredChild && "pointer-events-none",
          )}
          onClick={(e) => {
            if (isGithubStarredChild) {
              e.preventDefault();
              return;
            }
            handleUserTrack("github_starred");
          }}
        >
          <div
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-[10px] hover:bg-muted",
              isGithubStarredChild && "pointer-events-none",
            )}
          >
            {isGithubStarredChild ? (
              <span data-testid="github_starred_icon_get_started">
                <IconComponent
                  name="Check"
                  className="h-4 w-4 text-accent-emerald-foreground"
                />
              </span>
            ) : (
              <FaGithub className="h-4 w-4" />
            )}
            <span
              className={cn(
                "text-sm",
                isGithubStarredChild && "text-muted-foreground line-through",
              )}
            >
              Star repo for updates
            </span>
          </div>
        </Button>

        <Button
          data-testid="discord_joined_btn_get_started"
          unstyled
          className={cn(
            "w-full",
            isDiscordJoinedChild && "pointer-events-none",
          )}
          onClick={(e) => {
            if (isDiscordJoinedChild) {
              e.preventDefault();
              return;
            }
            handleUserTrack("discord_clicked");
          }}
        >
          <div
            className={cn(
              "flex items-center gap-2 rounded-md p-2 py-[10px] hover:bg-muted",
              isDiscordJoinedChild && "pointer-events-none",
            )}
          >
            {isDiscordJoinedChild ? (
              <span data-testid="discord_joined_icon_get_started">
                <IconComponent
                  name="Check"
                  className="h-4 w-4 text-accent-emerald-foreground"
                />
              </span>
            ) : (
              <FaDiscord className="h-4 w-4 text-[#5865F2]" />
            )}
            <span
              className={cn(
                "text-sm",
                isDiscordJoinedChild && "text-muted-foreground line-through",
              )}
            >
              Join the community
            </span>
          </div>
        </Button>

        <Button
          unstyled
          className={cn("w-full", hasFlows && "pointer-events-none")}
          onClick={() => setNewProjectModal(true)}
        >
          <div
            className={cn(
              "flex items-center gap-2 rounded-md p-2 py-[10px] hover:bg-muted",
              hasFlows && "pointer-events-none text-muted-foreground",
            )}
            data-testid="create_flow_btn_get_started"
          >
            <span data-testid="create_flow_icon_get_started">
              <IconComponent
                name={hasFlows ? "Check" : "Plus"}
                className={cn(
                  "h-4 w-4 text-primary",
                  hasFlows && "text-accent-emerald-foreground",
                )}
              />
            </span>
            <span className={cn("text-sm", hasFlows && "line-through")}>
              Create a flow
            </span>
          </div>
        </Button>
      </div>

      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => {}}
        handleDeleteFolder={() => {}}
      />
    </div>
  );
};
