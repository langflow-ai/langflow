import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { AudioLines, Mic } from "lucide-react";
import { FC } from "react";

interface VoiceButtonProps {
  isRecording: boolean;
  toggleRecording: () => void;
  lockChat?: boolean;
}

const VoiceButton = ({
  isRecording,
  toggleRecording,
  lockChat = false,
}: VoiceButtonProps) => {
  return (
    <>
      <div>
        <Button
          onClick={toggleRecording}
          disabled={lockChat}
          className={`btn-playground-actions ${
            lockChat
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
