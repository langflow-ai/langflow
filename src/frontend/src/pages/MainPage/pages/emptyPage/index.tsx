import ShortLangFlowIcon from "@/components/appHeaderComponent/assets//ShortLangFlowIcon.svg?react";
import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ENABLE_NEW_LOGO } from "@/customization/feature-flags";
import { useFolderStore } from "@/stores/foldersStore";
import { PaginatedFolderType } from "../../entities";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
  setShowFolderModal: (open: boolean) => void;
  folderData: PaginatedFolderType | null;
};

export const EmptyPage = ({
  setOpenModal,
  setShowFolderModal,
  folderData,
}: EmptyPageProps) => {
  const folders = useFolderStore((state) => state.folders);

  return (
    <div className="m-0 p-0">
      <div className="text-container">
        {(folderData?.folder?.name && folderData?.flows?.items?.length !== 0) ||
          (folders?.length > 1 && (
            <div className="absolute left-10 top-10 flex items-center text-2xl font-semibold dark:text-white">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowFolderModal(true)}
                className="mr-2 bg-transparent lg:hidden"
              >
                <ForwardedIconComponent
                  name="panel-left-open"
                  aria-hidden="true"
                  className="h-5 w-5 text-zinc-500 dark:text-zinc-400"
                />
              </Button>
              {folderData?.folder?.name}
            </div>
          ))}
        <div className="relative z-20 flex w-full flex-col items-center justify-center gap-2">
          {ENABLE_NEW_LOGO ? (
            <ShortLangFlowIcon className="h-7 w-7 fill-black dark:fill-[white]" />
          ) : (
            <span className="fill-black text-4xl dark:fill-white">⛓️</span>
          )}
          <h3
            className="pt-5 text-2xl font-semibold dark:text-white"
            style={{
              fontFamily: "Chivo",
            }}
            data-testid="mainpage_title"
          >
            {folders?.length > 1 ? "Empty folder" : "Start building"}
          </h3>
          <p className="pb-5 text-sm dark:text-white">
            Begin with a template, or start from scratch.
          </p>
          <Button
            variant="default"
            onClick={() => setOpenModal(true)}
            id="new-project-btn"
          >
            <ForwardedIconComponent
              name="plus"
              aria-hidden="true"
              className="h-4 w-4"
            />
            <span className="hidden whitespace-nowrap font-semibold md:inline">
              New Flow
            </span>
          </Button>
        </div>
      </div>
      {folders?.length === 1 && (
        <div className="gradient-bg">
          <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
            <defs>
              <filter id="lf-balls">
                <feGaussianBlur
                  in="turbulence"
                  stdDeviation="10"
                  result="blur"
                />
                <feColorMatrix
                  in="blur"
                  type="matrix"
                  values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -8"
                  result="color-matrix"
                />
                <feBlend in="SourceGraphic" in2="color-matrix" mode="normal" />
              </filter>
              <filter id="lf-noise">
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency="0.65"
                  stitchTiles="stitch"
                />
              </filter>
            </defs>
          </svg>
          <div className="gradients-container">
            <div className="g1" />
            <div className="g2" />
            <div className="g3" />
            <div className="g4" />
            <div className="g5" />
            <div className="g6" />
          </div>
        </div>
      )}
    </div>
  );
};

export default EmptyPage;
