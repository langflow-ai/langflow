import { MutableRefObject } from "react";

export const useStartRecording = async (
  audioContextRef: MutableRefObject<AudioContext | null>,
  microphoneRef: MutableRefObject<MediaStreamAudioSourceNode | null>,
  analyserRef: MutableRefObject<AnalyserNode | null>,
  wsRef: MutableRefObject<WebSocket | null>,
  setIsRecording: (isRecording: boolean) => void,
  playNextAudioChunk: () => void,
  isPlayingRef: MutableRefObject<boolean>,
  audioQueueRef: MutableRefObject<AudioBuffer[]>,
  workletCode: string,
  processorRef: MutableRefObject<AudioWorkletNode | null>,
  setStatus: (status: string) => void,
) => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!audioContextRef.current) return;

    microphoneRef.current =
      audioContextRef.current.createMediaStreamSource(stream);
    analyserRef.current = audioContextRef.current.createAnalyser();
    microphoneRef.current.connect(analyserRef.current);

    const blob = new Blob([workletCode], { type: "application/javascript" });
    const workletUrl = URL.createObjectURL(blob);

    try {
      await audioContextRef.current.audioWorklet.addModule(workletUrl);
      processorRef.current = new AudioWorkletNode(
        audioContextRef.current,
        "stream_processor",
      );

      analyserRef.current.connect(processorRef.current);
      processorRef.current.connect(audioContextRef.current.destination);

      processorRef.current.port.onmessage = (event) => {
        if (event.data.type === "input" && event.data.audio && wsRef.current) {
          const base64Audio = btoa(
            String.fromCharCode.apply(
              null,
              Array.from(new Uint8Array(event.data.audio.buffer)),
            ),
          );

          wsRef.current.send(
            JSON.stringify({
              type: "input_audio_buffer.append",
              audio: base64Audio,
            }),
          );
        } else if (event.data.type === "done") {
          if (audioQueueRef.current.length > 0) {
            playNextAudioChunk();
          } else {
            isPlayingRef.current = false;
          }
        }
      };

      setIsRecording(true);
    } catch (err) {
      console.error("AudioWorklet failed to load:", err);
      throw err;
    } finally {
      URL.revokeObjectURL(workletUrl);
    }
  } catch (err) {
    console.error("Error accessing microphone:", err);
    setStatus("Error: " + (err as Error).message);
  }
};
