import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";
import { useEffect, useRef } from "react";
import LangflowEmptyIcon from "../../assets/LangflowEmptyIcon.svg?react";
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
  const interBubbleRef = useRef<HTMLDivElement>(null);
  const folders = useFolderStore((state) => state.folders);

  useEffect(() => {
    const interBubble = interBubbleRef.current;
    const aside = document.querySelector("aside"); // Adjust this selector to target your aside

    if (!interBubble || !aside) return;

    let curX = 0;
    let curY = 0;
    let tgX = 0;
    let tgY = 0;

    const move = () => {
      curX += (tgX - curX) / 20;
      curY += (tgY - curY) / 20;
      interBubble.style.transform = `translate(${Math.round(curX)}px, ${Math.round(curY)}px)`;
      requestAnimationFrame(move);
    };

    const handleMouseMove = (event: MouseEvent) => {
      const asideRect = aside.getBoundingClientRect();
      const asideWidth = asideRect.width;

      // Adjust for the aside's dynamic width
      tgX = event.clientX - asideWidth;
      tgY = event.clientY;
    };

    window.addEventListener("mousemove", handleMouseMove);
    move();

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  console.log(folders?.length, "folders");

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
          <LangflowEmptyIcon />
          <h3 className="pt-5 text-2xl font-semibold dark:text-white">
            Start building
          </h3>
          <p className="pb-2 text-sm dark:text-white">
            Begin with a template, or start from scratch.
          </p>
          <Button id="new-project-btn" onClick={() => setOpenModal(true)}>
            New Flow
          </Button>
        </div>
      </div>
      <div className="gradient-bg">
        <svg xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="goo">
              <feGaussianBlur
                in="SourceGraphic"
                stdDeviation="10"
                result="blur"
              />
              <feColorMatrix
                in="blur"
                mode="matrix"
                values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -8"
                result="goo"
              />
              <feBlend in="SourceGraphic" in2="goo" />
            </filter>
          </defs>
        </svg>
        <div className="gradients-container">
          <div className="g1" />
          <div className="g2" />
          <div className="g3" />
          <div className="g4" />
          <div className="g5" />
          <div className="interactive" ref={interBubbleRef} />
        </div>
      </div>
    </div>
  );
};

export default EmptyPage;
