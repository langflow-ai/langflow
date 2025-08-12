export const useStopRecording = (
  microphoneRef,
  processorRef: React.MutableRefObject<AudioWorkletNode | null>,
  analyserRef: React.MutableRefObject<AnalyserNode | null>,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setIsRecording: (isRecording: boolean) => void,
) => {
  if (microphoneRef.current) {
    microphoneRef.current.disconnect();
    microphoneRef.current = null;
  }
  if (processorRef.current) {
    processorRef.current.disconnect();
    processorRef.current = null;
  }
  if (analyserRef.current) {
    analyserRef.current.disconnect();
    analyserRef.current = null;
  }
  if (wsRef.current) {
    wsRef.current.close();
    wsRef.current = null;
  }
  setIsRecording(false);
};
