import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import type { AudioRecordingState } from "../hooks/use-audio-recording";

interface AudioButtonProps {
  isBuilding: boolean;
  recordingState: AudioRecordingState;
  onStartRecording: () => void;
  onStopRecording: () => void;
  isSupported: boolean;
}

const AudioButton = ({
  isBuilding,
  recordingState,
  onStartRecording,
  onStopRecording,
  isSupported,
}: AudioButtonProps) => {
  const isRecording = recordingState === "recording";
  const isProcessing = recordingState === "processing";
  const isDisabled = isBuilding || isProcessing || !isSupported;

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (isRecording) {
      onStopRecording();
    } else {
      onStartRecording();
    }
  };

  const getTooltipContent = () => {
    if (!isSupported) return "Voice input not supported in this browser";
    if (isRecording) return "Stop recording";
    if (isProcessing) return "Processing...";
    return "Voice input";
  };

  return (
    <ShadTooltip styleClasses="z-50" side="top" content={getTooltipContent()}>
      <div>
        <Button
          disabled={isDisabled}
          className={cn(
            "h-7 w-7 px-0 flex items-center justify-center transition-all duration-200",
            isDisabled && "cursor-not-allowed opacity-50",
            isRecording &&
              "text-destructive hover:text-destructive animate-pulse duration-1000",
            !isRecording &&
              !isDisabled &&
              "text-muted-foreground hover:text-primary",
          )}
          onClick={handleClick}
          unstyled
          data-testid="audio-button"
        >
          <ForwardedIconComponent
            className={cn(
              "h-[18px] w-[18px]",
              isRecording && "text-destructive",
            )}
            name={isRecording ? "MicOff" : "Mic"}
          />
        </Button>
      </div>
    </ShadTooltip>
  );
};

export default AudioButton;
