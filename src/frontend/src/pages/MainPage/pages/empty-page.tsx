import { ExternalLink } from "lucide-react";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { useShallow } from "zustand/react/shallow";
import logoDarkPng from "@/assets/logo_dark.png";
import logoLightPng from "@/assets/logo_light.png";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { Button } from "@/components/ui/button";
import { DotBackgroundDemo } from "@/components/ui/dot-background";
import { DISCORD_URL, GITHUB_URL } from "@/constants/constants";
import { useGetUserData, useUpdateUser } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { useFolderStore } from "@/stores/foldersStore";
import { formatNumber } from "@/utils/utils";
import useFileDrop from "../hooks/use-on-file-drop";

const EMPTY_PAGE_TITLE = "Welcome to Langflow";
const EMPTY_PAGE_DESCRIPTION = "Your new favorite way to ship Agents";
const EMPTY_PAGE_GITHUB_DESCRIPTION =
  "Follow development, star the repo, and shape the future.";
const EMPTY_PAGE_DISCORD_DESCRIPTION =
  "Join builders, ask questions, and show off your agents";
const EMPTY_PAGE_DRAG_AND_DROP_TEXT =
  "Already have a flow? Drag and drop to upload.";
const EMPTY_PAGE_FOLDER_DESCRIPTION = "Empty folder";
const EMPTY_PAGE_CREATE_FIRST_FLOW_BUTTON_TEXT = "Create first flow";

const EXTERNAL_LINK_ICON_CLASS =
  "absolute right-6 top-[35px] h-4 w-4 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";

export const EmptyPageCommunity = ({
  setOpenModal,
}: {
  setOpenModal: (open: boolean) => void;
}) => {
  const handleFileDrop = useFileDrop(undefined);
  const folders = useFolderStore((state) => state.folders);
  const userData = useAuthStore(useShallow((state) => state.userData));
  const stars: number | undefined = useDarkStore((state) => state.stars);
  const discordCount: number = useDarkStore((state) => state.discordCount);
  const { mutate: updateUser } = useUpdateUser();
  const { mutate: mutateLoggedUser } = useGetUserData();

  const handleUserTrack = (key: string) => () => {
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
        },
      },
    );
  };

  return (
    <DotBackgroundDemo>
      <CardsWrapComponent
        dragMessage={`Drop your flows or components here`}
        onFileDrop={handleFileDrop}
      >
        <div className="m-0 h-full w-full bg-background p-0">
          <div className="z-50 flex h-full w-full flex-col items-center justify-center gap-5">
            <div className="z-50 flex flex-col items-center gap-2">
              <div className="z-50 dark:hidden">
                <img
                  src={logoLightPng}
                  alt="Langflow Logo Light"
                  data-testid="empty_page_logo_light"
                  className="relative top-8 h-40 pointer-events-none select-none"
                />
              </div>
              <div className="z-50 hidden dark:block">
                <img
                  src={logoDarkPng}
                  alt="Langflow Logo Dark"
                  data-testid="empty_page_logo_dark"
                  className="relative top-8 h-40 pointer-events-none select-none"
                />
              </div>
              <span
                data-testid="mainpage_title"
                className="z-50 text-center font-chivo text-2xl font-medium text-foreground"
              >
                {EMPTY_PAGE_TITLE}
              </span>

              <span
                data-testid="empty_page_description"
                className="z-50 text-center text-base text-secondary-foreground"
              >
                {folders?.length > 1
                  ? EMPTY_PAGE_FOLDER_DESCRIPTION
                  : EMPTY_PAGE_DESCRIPTION}
              </span>
            </div>

            <div className="flex w-full max-w-[510px] flex-col gap-7 sm:gap-[29px]">
              <Button
                unstyled
                className="group mx-3 h-[84px] sm:mx-0"
                onClick={() => {
                  handleUserTrack("github_starred")();
                  window.open(GITHUB_URL, "_blank", "noopener,noreferrer");
                }}
                data-testid="empty_page_github_button"
              >
                <div className="relative flex flex-col rounded-lg border-[1px] bg-background p-4 transition-all duration-300 hover:border-accent-pink-foreground">
                  <div className="grid w-full items-center justify-between gap-2">
                    <div className="flex gap-3">
                      <FaGithub className="h-6 w-6" />
                      <div>
                        <span className="font-semibold">GitHub</span>
                        <span className="ml-2 font-mono text-muted-foreground">
                          {formatNumber(stars)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-base text-secondary-foreground">
                        {EMPTY_PAGE_GITHUB_DESCRIPTION}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className={EXTERNAL_LINK_ICON_CLASS} />
                </div>
              </Button>

              <Button
                unstyled
                className="group mx-3 h-[84px] sm:mx-0"
                onClick={() => {
                  handleUserTrack("discord_clicked")();
                  window.open(DISCORD_URL, "_blank", "noopener,noreferrer");
                }}
                data-testid="empty_page_discord_button"
              >
                <div className="relative flex flex-col rounded-lg border-[1px] bg-background p-4 transition-all duration-300 hover:border-discord-color">
                  <div className="grid w-full items-center justify-between gap-2">
                    <div className="flex gap-3">
                      <FaDiscord className="h-6 w-6 text-discord-color" />
                      <div>
                        <span className="font-semibold">Discord</span>
                        <span className="ml-2 font-mono text-muted-foreground">
                          {formatNumber(discordCount)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-base text-secondary-foreground">
                        {EMPTY_PAGE_DISCORD_DESCRIPTION}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className={EXTERNAL_LINK_ICON_CLASS} />
                </div>
              </Button>

              <Button
                variant="default"
                className="z-10 m-auto mt-3 h-10 w-full max-w-[10rem] rounded-lg font-bold transition-all duration-300"
                onClick={() => setOpenModal(true)}
                id="new-project-btn"
                data-testid="new_project_btn_empty_page"
              >
                <ForwardedIconComponent
                  name="Plus"
                  aria-hidden="true"
                  className="h-4 w-4"
                />
                <span>{EMPTY_PAGE_CREATE_FIRST_FLOW_BUTTON_TEXT}</span>
              </Button>
            </div>
          </div>
        </div>
        <p
          data-testid="empty_page_drag_and_drop_text"
          className="absolute bottom-5 left-0 right-0 mt-4 cursor-default text-center text-xxs text-muted-foreground"
        >
          {EMPTY_PAGE_DRAG_AND_DROP_TEXT}
        </p>
      </CardsWrapComponent>
    </DotBackgroundDemo>
  );
};

export default EmptyPageCommunity;
