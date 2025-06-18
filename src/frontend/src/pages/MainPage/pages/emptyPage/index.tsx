import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";
import useFileDrop from "../../hooks/use-on-file-drop";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyPage = ({ setOpenModal }: EmptyPageProps) => {
  const folders = useFolderStore((state) => state.folders);
  const handleFileDrop = useFileDrop(undefined);

  return (
    <CardsWrapComponent
      dragMessage={`Drop your flows or components here`}
      onFileDrop={handleFileDrop}
    >
      <div className="m-0 h-full w-full bg-secondary p-0">
        <div className="text-container">
          <div className="relative z-20 flex w-full flex-col items-center justify-center gap-2">
            <LangflowLogo className="h-7 w-8" />
            <h3
              className="pt-5 font-chivo text-2xl font-semibold text-foreground"
              data-testid="mainpage_title"
            >
              {folders?.length > 1 ? "Empty project" : "Start building"}
            </h3>
            <p
              data-testid="empty-project-description"
              className="pb-5 text-sm text-secondary-foreground"
            >
              Begin with a template, or start from scratch.
            </p>
            <Button
              variant="default"
              onClick={() => setOpenModal(true)}
              id="new-project-btn"
              data-testid="new_project_btn_empty_page"
            >
              <ForwardedIconComponent
                name="Plus"
                aria-hidden="true"
                className="h-4 w-4"
              />
              <span className="hidden whitespace-nowrap font-semibold md:inline">
                New Flow
              </span>
            </Button>
          </div>
        </div>
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
      </div>
    </CardsWrapComponent>
  );
};

export default EmptyPage;
