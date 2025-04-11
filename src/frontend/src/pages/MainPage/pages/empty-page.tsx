import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { BackgroundGradient } from "@/components/ui/background-gradient";
import { Button } from "@/components/ui/button";
import { DotBackgroundDemo } from "@/components/ui/dot-background";
import { useFolderStore } from "@/stores/foldersStore";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { HiArrowRight } from "react-icons/hi";
import useFileDrop from "../hooks/use-on-file-drop";

const ARROW_GITHUB_ICON_CLASS =
  "relative left-10 top-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";
const ARROW_DISCORD_ICON_CLASS =
  "relative left-20 top-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100";
const BACKGROUND_GRADIENT_CLASS =
  "z-50 group overflow-hidden relative h-[100px] cursor-pointer content-center items-center justify-between rounded-3xl border border-border bg-background transition-colors hover:bg-muted";

export const EmptyPageCommunity = ({
  setOpenModal,
}: {
  setOpenModal: (open: boolean) => void;
}) => {
  const handleFileDrop = useFileDrop(undefined);
  const folders = useFolderStore((state) => state.folders);

  return (
    <DotBackgroundDemo>
      <CardsWrapComponent
        dragMessage={`Drop your flows or components here`}
        onFileDrop={handleFileDrop}
      >
        <div className="m-0 h-full w-full bg-background p-0">
          <div className="z-50 flex h-full flex-col items-center justify-center gap-8">
            <div className="z-50 flex flex-col items-center gap-3">
              <LangflowLogo className="mb-4 h-[18px] w-5" />
              <h1 className="z-50 text-lg font-semibold text-primary">
                Welcome to Langflow
              </h1>

              <p className="z-50 text-sm text-muted-foreground">
                {folders?.length > 1 ? "Empty folder" : "Let's get started"}
              </p>
            </div>

            <div className="flex w-full max-w-[352px] flex-col gap-7">
              <a
                href="https://github.com/logspace-ai/langflow"
                target="_blank"
                rel="noreferrer"
                className="block"
              >
                <BackgroundGradient
                  className={BACKGROUND_GRADIENT_CLASS}
                  containerClassName="bg-gradient-to-r from-pink-500/30 via-transparent to-purple-500/30 z-50"
                >
                  <DotBackgroundDemo
                    className="rounded-3xl"
                    containerClassName="rounded-3xl"
                  >
                    <div className="relative right-4 top-6 z-50 flex h-full flex-col">
                      <div className="z-50 flex w-full items-center justify-between">
                        <div className="z-50 flex items-center gap-3">
                          <FaGithub className="z-50 h-6 w-6" />
                          <div>
                            <span className="z-50 font-medium">GitHub</span>
                            <span className="z-50 ml-2 text-muted-foreground">
                              55k
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
              </a>
              <a
                href="https://discord.gg/EqNEEadtZ2"
                target="_blank"
                rel="noreferrer"
                className="block"
              >
                <BackgroundGradient
                  className={BACKGROUND_GRADIENT_CLASS}
                  containerClassName="bg-gradient-to-r from-blue-500/30 via-transparent to-indigo-500/30"
                >
                  <DotBackgroundDemo
                    className="rounded-3xl"
                    containerClassName="rounded-3xl"
                  >
                    <div className="relative right-9 top-6 z-50 flex h-full flex-col">
                      <div className="z-50 flex w-full items-center justify-between">
                        <div className="z-50 flex items-center gap-3">
                          <FaDiscord className="z-50 h-6 w-6 text-[#5765F2]" />

                          <div>
                            <span className="z-50 font-medium">Discord</span>
                            <span className="z-50 ml-2 text-muted-foreground">
                              55k
                            </span>
                          </div>
                        </div>
                        <HiArrowRight className={ARROW_DISCORD_ICON_CLASS} />
                      </div>
                      <div className="z-50 mt-2">
                        <span className="z-50 text-[13px] text-muted-foreground">
                          Chat, share, and build together
                        </span>
                      </div>
                    </div>
                  </DotBackgroundDemo>
                </BackgroundGradient>
              </a>

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
