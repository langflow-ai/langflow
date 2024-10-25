import { Button } from "@/components/ui/button";
import { useEffect } from "react";
import LangflowEmptyIcon from "../../assets/LangflowEmptyIcon.svg?react";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyPage = ({ setOpenModal }: EmptyPageProps) => {
  useEffect(() => {
    const interBubble = document.querySelector<HTMLDivElement>(".interactive");
    if (!interBubble) return;

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
      tgX = event.clientX;
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
        <div className="relative z-20 flex h-full w-full flex-col items-center justify-center gap-2">
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
          <div className="g1"></div>
          <div className="g2"></div>
          <div className="g3"></div>
          <div className="g4"></div>
          <div className="g5"></div>
          <div className="interactive"></div>
        </div>
      </div>
    </div>
  );
};

export default EmptyPage;
