import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

interface SettingsVoiceButtonProps {
  isRecording: boolean;
  setShowSettingsModal: (value: boolean) => void;
}

const SettingsVoiceButton = ({
  isRecording,
  setShowSettingsModal,
}: SettingsVoiceButtonProps) => {
  return (
    <>
      <ShadTooltip content="Audio Settings" side="top">
        <div>
          <Button
            className={`btn-playground-actions text-muted-foreground hover:text-primary cursor-pointer`}
            unstyled
            disabled={isRecording}
            onClick={() => setShowSettingsModal(true)}
          >
            <ForwardedIconComponent
              className={`h-[18px] w-[18px]`}
              name={"Wrench"}
            />
          </Button>
        </div>
      </ShadTooltip>
    </>
  );
};

export default SettingsVoiceButton;
