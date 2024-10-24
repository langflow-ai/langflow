import { Button } from "@/components/ui/button";
import LangflowEmptyIcon from "../../assets/LangflowEmptyIcon.svg?react";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyPage = ({ setOpenModal }: EmptyPageProps) => {
  return (
    <div className="relative h-full w-full">
      <div className="relative h-full w-full">
        <div className="absolute left-5 top-5 z-20 font-bold text-white">
          My projects
        </div>
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
    </div>
  );
};

export default EmptyPage;
