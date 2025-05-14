import {
  VoiceAssistant,
  VoiceAssistantProps,
} from "@/modals/IOModal/components/chatView/chatInput/components/voice-assistant/voice-assistant";

export function CustomVoiceAssistant({
  flowId,
  setShowAudioInput,
}: VoiceAssistantProps) {
  return (
    <VoiceAssistant flowId={flowId} setShowAudioInput={setShowAudioInput} />
  );
}

export default CustomVoiceAssistant;
