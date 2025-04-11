import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { HiArrowRight } from "react-icons/hi";
import useFileDrop from "../hooks/use-on-file-drop";

const ARROW_ICON_CLASS =
  "relative right-5 top-4 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100";
const A_TAG_CLASS =
  "group h-[100px] content-center items-center justify-between rounded-3xl border border-border bg-background py-4 px-6 transition-colors hover:bg-muted";

export const EmptyPageCommunity = ({
  setOpenModal,
}: {
  setOpenModal: (open: boolean) => void;
}) => {
  const handleFileDrop = useFileDrop(undefined);
  const folders = useFolderStore((state) => state.folders);

  return (
    <CardsWrapComponent
      dragMessage={`Drop your flows or components here`}
      onFileDrop={handleFileDrop}
    >
      <div className="m-0 h-full w-full bg-background p-0">
        <div className="flex h-full flex-col items-center justify-center gap-8">
          <div className="flex flex-col items-center gap-3">
            <LangflowLogo className="mb-4 h-[18px] w-5" />
            <h1 className="text-lg font-semibold text-primary">
              Welcome to Langflow
            </h1>

            <p className="text-sm text-muted-foreground">
              {folders?.length > 1 ? "Empty folder" : "Let's get started"}
            </p>
          </div>

          <div className="flex w-full max-w-[352px] flex-col gap-4">
            <a
              href="https://github.com/logspace-ai/langflow"
              target="_blank"
              rel="noopener noreferrer"
              className={A_TAG_CLASS}
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-3">
                  <FaGithub className="h-6 w-6" />
                  <div>
                    <span className="font-medium">GitHub</span>
                    <span className="ml-2 text-muted-foreground">55k</span>
                  </div>
                </div>
                <HiArrowRight className={ARROW_ICON_CLASS} />
              </div>
              <div className="mt-2">
                <span className="text-[13px] text-muted-foreground">
                  Star the project and follow our journey
                </span>
              </div>
            </a>

            <a
              href="https://discord.gg/langflow"
              target="_blank"
              rel="noopener noreferrer"
              className={A_TAG_CLASS}
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-3">
                  <FaDiscord className="h-6 w-6 text-[#5765F2]" />
                  <div>
                    <span className="font-medium">Discord</span>
                    <span className="ml-2 text-muted-foreground">12k</span>
                  </div>
                </div>

                <HiArrowRight className={ARROW_ICON_CLASS} />
              </div>
              <div className="mt-2">
                <span className="text-[13px] text-muted-foreground">
                  Chat, share, and build together
                </span>
              </div>
            </a>

            <Button
              variant="default"
              className="w-full font-bold"
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
  );
};

export default EmptyPageCommunity;
