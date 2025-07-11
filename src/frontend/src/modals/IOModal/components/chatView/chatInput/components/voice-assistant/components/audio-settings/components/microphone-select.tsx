import { useEffect } from "react";
import IconComponent from "../../../../../../../../../../components/common/genericIconComponent";
import ShadTooltip from "../../../../../../../../../../components/common/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../../../../../../../components/ui/select";

interface MicrophoneSelectProps {
  selectedMicrophone: string;
  handleSetMicrophone: (value: string) => void;
  microphones: MediaDeviceInfo[];
  setMicrophones: (microphones: MediaDeviceInfo[]) => void;
  setSelectedMicrophone: (microphone: string) => void;
}

const MicrophoneSelect = ({
  selectedMicrophone,
  handleSetMicrophone,
  microphones,
  setMicrophones,
  setSelectedMicrophone,
}: MicrophoneSelectProps) => {
  useEffect(() => {
    const getMicrophones = async () => {
      try {
        await navigator?.mediaDevices?.getUserMedia({ audio: true });

        const devices = await navigator?.mediaDevices?.enumerateDevices();
        const audioInputDevices = devices?.filter(
          (device) => device.kind === "audioinput",
        );
        setMicrophones(audioInputDevices);

        if (audioInputDevices.length > 0 && !selectedMicrophone) {
          const savedMicrophoneId = localStorage.getItem(
            "lf_selected_microphone",
          );
          if (
            savedMicrophoneId &&
            audioInputDevices.some(
              (device) => device.deviceId === savedMicrophoneId,
            )
          ) {
            setSelectedMicrophone(savedMicrophoneId);
          } else {
            setSelectedMicrophone(audioInputDevices[0].deviceId);
          }
        }
      } catch (error) {
        console.error("Error accessing media devices:", error);
      }
    };

    getMicrophones();

    navigator?.mediaDevices?.addEventListener("devicechange", getMicrophones);

    return () => {
      navigator?.mediaDevices?.removeEventListener(
        "devicechange",
        getMicrophones,
      );
    };
  }, []);

  return (
    <div
      className="grid w-full items-center gap-2"
      data-testid="voice-assistant-settings-modal-microphone-select"
    >
      <span className="flex w-full items-center text-sm">
        Audio Input
        <ShadTooltip content="Select which microphone to use for voice input">
          <div>
            <IconComponent
              name="Info"
              strokeWidth={2}
              className="text-placeholder relative -top-[3px] left-1 h-[14px] w-[14px]"
            />
          </div>
        </ShadTooltip>
      </span>

      <Select value={selectedMicrophone} onValueChange={handleSetMicrophone}>
        <SelectTrigger className="h-9 w-full">
          <SelectValue placeholder="Select microphone" />
        </SelectTrigger>
        <SelectContent className="max-h-[200px]">
          <SelectGroup>
            {microphones?.map((device) => (
              <SelectItem key={device?.deviceId} value={device?.deviceId}>
                <div className="max-w-[220px] truncate text-left">
                  {device?.label ||
                    `Microphone ${device?.deviceId?.slice(0, 5)}...`}
                </div>
              </SelectItem>
            ))}
            {microphones?.length === 0 && (
              <SelectItem value="no-microphones" disabled>
                No microphones found
              </SelectItem>
            )}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

export default MicrophoneSelect;
