import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { AudioLines, Mic } from "lucide-react";
import { FC } from "react";

interface VoiceButtonProps {
  isRecording: boolean;
  toggleRecording: () => void;
  isBuilding?: boolean;
}

const VoiceButton = ({
  isRecording,
  toggleRecording,
  isBuilding = false,
}: VoiceButtonProps) => {
  return (
    <>
      <div>
        <Button
          onClick={toggleRecording}
          disabled={isBuilding}
          className={`btn-playground-actions ${
            isBuilding
              ? "cursor-not-allowed"
              : "text-muted-foreground hover:text-primary"
          }`}
          unstyled
        >
          <ForwardedIconComponent className="h-[18px] w-[18px]" name={"Mic"} />
        </Button>
      </div>
    </>
  );
};

export default VoiceButton;
