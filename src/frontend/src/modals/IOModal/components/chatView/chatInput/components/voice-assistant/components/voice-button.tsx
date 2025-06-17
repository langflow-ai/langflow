import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useVoiceStore } from "@/stores/voiceStore";

interface VoiceButtonProps {
  toggleRecording: () => void;
}

const VoiceButton = ({ toggleRecording }: VoiceButtonProps) => {
  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );
  const voiceModeEnabled = useFlowsManagerStore(
    (state) => state.voiceModeEnabled,
  );

  if (!voiceModeEnabled) {
    return null;
  }

  return (
    <>
      <div>
        <Button
          onClick={() => {
            toggleRecording();
            setNewSessionCloseVoiceAssistant(false);
          }}
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
