import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";

interface VoiceButtonProps {
  toggleRecording: () => void;
}

const VoiceButton = ({ toggleRecording }: VoiceButtonProps) => {
  return (
    <>
      <div>
        <Button
          onClick={toggleRecording}
          className="btn-playground-actions group"
          unstyled
          data-testid="voice-button"
        >
          <ForwardedIconComponent
            className={
              "icon-size text-muted-foreground group-hover:text-primary"
            }
            name={"Mic"}
            strokeWidth={ICON_STROKE_WIDTH}
          />
        </Button>
      </div>
    </>
  );
};

export default VoiceButton;
