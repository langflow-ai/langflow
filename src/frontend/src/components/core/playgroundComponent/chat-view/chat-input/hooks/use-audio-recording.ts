import { useCallback, useRef, useState } from "react";

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: ((this: SpeechRecognition, ev: Event) => void) | null;
  onend: ((this: SpeechRecognition, ev: Event) => void) | null;
  onerror:
    | ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => void)
    | null;
  onresult:
    | ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void)
    | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type AudioRecordingState = "idle" | "recording" | "processing";

interface UseAudioRecordingOptions {
  onTranscriptionComplete: (transcribedText: string) => void;
  onError?: (error: string) => void;
}

interface UseAudioRecordingReturn {
  state: AudioRecordingState;
  startRecording: () => void;
  stopRecording: () => void;
  cancelRecording: () => void;
  isRecording: boolean;
  isSupported: boolean;
}

// Check if the browser supports speech recognition
const getSpeechRecognition = (): (new () => SpeechRecognition) | undefined => {
  if (typeof window === "undefined") return undefined;
  return (
    (window as Window & { SpeechRecognition?: new () => SpeechRecognition })
      .SpeechRecognition ||
    (
      window as Window & {
        webkitSpeechRecognition?: new () => SpeechRecognition;
      }
    ).webkitSpeechRecognition
  );
};

export function useAudioRecording({
  onTranscriptionComplete,
  onError,
}: UseAudioRecordingOptions): UseAudioRecordingReturn {
  const [state, setState] = useState<AudioRecordingState>("idle");
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const transcriptRef = useRef<string>("");
  const isActiveRef = useRef<boolean>(false);

  const SpeechRecognitionClass = getSpeechRecognition();
  const isSupported = !!SpeechRecognitionClass;

  const startRecording = useCallback(() => {
    if (!SpeechRecognitionClass) {
      onError?.(
        "Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.",
      );
      return;
    }

    try {
      const recognition = new SpeechRecognitionClass();
      recognitionRef.current = recognition;
      transcriptRef.current = "";
      isActiveRef.current = true;

      // Configure speech recognition
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = navigator.language || "en-US";

      recognition.onstart = () => {
        setState("recording");
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          }
        }

        // Accumulate final transcripts
        if (finalTranscript) {
          transcriptRef.current += finalTranscript;
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        isActiveRef.current = false;
        recognitionRef.current = null;
        setState("idle");

        switch (event.error) {
          case "not-allowed":
            onError?.(
              "Microphone access denied. Please allow microphone access in your browser settings.",
            );
            break;
          case "no-speech":
            // Don't show error for no-speech, just reset
            break;
          case "audio-capture":
            onError?.(
              "No microphone found. Please connect a microphone and try again.",
            );
            break;
          case "network":
            onError?.(
              "Network error occurred during speech recognition. Please check your connection.",
            );
            break;
          case "aborted":
            // User cancelled, no error needed
            break;
          default:
            onError?.(`Speech recognition error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        const wasActive = isActiveRef.current;
        isActiveRef.current = false;
        recognitionRef.current = null;

        if (wasActive) {
          const finalText = transcriptRef.current.trim();
          if (finalText) {
            onTranscriptionComplete(finalText);
          } else {
            onError?.("No speech was detected. Please try again.");
          }
        }

        setState("idle");
      };

      recognition.start();
    } catch (error) {
      isActiveRef.current = false;
      setState("idle");
      onError?.("Failed to start speech recognition. Please try again.");
    }
  }, [SpeechRecognitionClass, onTranscriptionComplete, onError]);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current && isActiveRef.current) {
      setState("processing");
      recognitionRef.current.stop();
    }
  }, []);

  const cancelRecording = useCallback(() => {
    isActiveRef.current = false;
    if (recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }
    transcriptRef.current = "";
    setState("idle");
  }, []);

  return {
    state,
    startRecording,
    stopRecording,
    cancelRecording,
    isRecording: state === "recording",
    isSupported,
  };
}
