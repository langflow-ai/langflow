import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { BackgroundGradient } from "@/components/ui/background-gradient";
import { Button } from "@/components/ui/button";
import { DotBackgroundDemo } from "@/components/ui/dot-background";
import { DISCORD_URL, GITHUB_URL } from "@/constants/constants";
import { useGetUserData, useUpdateUser } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { useFolderStore } from "@/stores/foldersStore";
import { formatNumber } from "@/utils/utils";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { HiArrowRight } from "react-icons/hi";
import { useShallow } from "zustand/react/shallow";
import useFileDrop from "../hooks/use-on-file-drop";

// const ARROW_GITHUB_ICON_CLASS =
//   "relative right-16 top-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";
const ARROW_DISCORD_ICON_CLASS =
  "relative left-28 top-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";
const ARROW_GITHUB_ICON_CLASS =
  "relative -right-10 top-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";
const BACKGROUND_GRADIENT_CLASS =
  "z-50 group overflow-hidden relative h-[100px] cursor-pointer content-center items-center justify-between rounded-3xl border border-border bg-background transition-colors hover:bg-muted";

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
          <div className="z-50 flex h-full w-full flex-col items-center justify-center">
            <div className="z-50 flex flex-col items-center gap-3">
              <LangflowLogo className="mb-4 h-[18px] w-5" />
              <span className="z-50 text-2xl font-semibold text-primary">
                Your new favorite way to ship Agents
              </span>

              <span className="z-50 font-[14px] text-muted-foreground">
                {folders?.length > 1
                  ? "Empty folder"
                  : "Design agents that connect to any API, model, or database."}
              </span>
            </div>

            <div className="flex w-full max-w-[352px] flex-col gap-7">
              <Button
                unstyled
                className="block"
                onClick={() => {
                  handleUserTrack("github_starred")();
                  window.open(GITHUB_URL, "_blank", "noopener,noreferrer");
                }}
              >
                <BackgroundGradient
                  className={BACKGROUND_GRADIENT_CLASS}
                  borderColor="#C661B8"
                >
                  <DotBackgroundDemo
                    className="rounded-3xl"
                    containerClassName="rounded-3xl"
                  >
                    <div className="relative right-[24px] top-6 z-50 flex h-full flex-col px-4">
                      <div className="z-50 flex w-full items-center justify-between">
                        <div className="z-50 flex items-center gap-3">
                          <FaGithub className="z-50 h-6 w-6" />
                          <div>
                            <span className="z-50 font-medium">GitHub</span>
                            <span className="z-50 ml-2 text-muted-foreground">
                              {formatNumber(stars)}
                            </span>
                          </div>
                        </div>
                        <HiArrowRight className={ARROW_GITHUB_ICON_CLASS} />
                      </div>
                      <div className="z-50 mt-2">
                        <span className="z-50 text-[13px] text-muted-foreground">
                          Star the project and follow our journey
                        </span>
                      </div>
                    </div>
                  </DotBackgroundDemo>
                </BackgroundGradient>
              </Button>
              <Button
                unstyled
                className="block"
                onClick={() => {
                  handleUserTrack("discord_clicked");
                  window.open(DISCORD_URL, "_blank", "noopener,noreferrer");
                }}
              >
                <BackgroundGradient
                  className={BACKGROUND_GRADIENT_CLASS}
                  borderColor="#5765F2"
                >
                  <DotBackgroundDemo
                    className="rounded-3xl"
                    containerClassName="rounded-3xl"
                  >
                    <div className="relative right-[60px] top-6 z-50 flex h-full flex-col">
                      <div className="z-50 flex w-full items-center justify-between">
                        <div className="z-50 flex items-center gap-3">
                          <FaDiscord className="z-50 h-6 w-6 text-[#5765F2]" />
                          <div>
                            <span className="z-50 font-medium">Discord</span>
                            <span className="z-50 ml-2 text-muted-foreground">
                              {formatNumber(discordCount)}
                            </span>
                          </div>
                        </div>
                        <HiArrowRight className={ARROW_DISCORD_ICON_CLASS} />
                      </div>
                      <div className="z-50 mt-2">
                        <span className="z-50 text-[13px] text-muted-foreground">
                          Get started with Langflow
                        </span>
                      </div>
                    </div>
                  </DotBackgroundDemo>
                </BackgroundGradient>
              </Button>

              <Button
                variant="default"
                className="z-10 w-full font-bold"
                onClick={() => setOpenModal(true)}
                id="new-project-btn"
                data-testid="new_project_btn_empty_page"
              >
                <span>+</span> Create first flow
              </Button>
            </div>
          </div>
        </div>
        <p className="absolute bottom-5 left-0 right-0 mt-4 cursor-default text-center text-sm text-muted-foreground">
          Already have a flow? Drag and drop to upload.
        </p>
      </CardsWrapComponent>
    </DotBackgroundDemo>
  );
};

export default EmptyPageCommunity;
