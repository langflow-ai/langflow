import { Button } from "@/components/ui/button";
import { useEffect, useRef } from "react";
import LangflowEmptyIcon from "../../assets/LangflowEmptyIcon.svg?react";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
  folderName: string;
};

export const EmptyPage = ({ setOpenModal, folderName }: EmptyPageProps) => {
  const interBubbleRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="m-0 p-0">
      <div className="text-container">
        <div className="absolute left-10 top-10 text-2xl font-semibold text-white">
          {folderName}
        </div>
        <div className="relative z-20 flex w-full flex-col items-center justify-center gap-2">
          <LangflowEmptyIcon />
          <h3 className="pt-5 text-2xl font-semibold text-white">
            Start building
          </h3>
          <p className="pb-2 text-sm text-white">
            Begin with a template, or start from scratch.
          </p>
          <Button onClick={() => setOpenModal(true)}>New Project</Button>
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
