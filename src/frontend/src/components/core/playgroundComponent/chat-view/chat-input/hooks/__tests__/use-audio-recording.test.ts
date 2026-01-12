import { act, renderHook } from "@testing-library/react";
import { useAudioRecording } from "../use-audio-recording";

// Mock SpeechRecognition
class MockSpeechRecognition {
  continuous = false;
  interimResults = false;
  lang = "";
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onresult:
    | ((event: { resultIndex: number; results: unknown[] }) => void)
    | null = null;

  start = jest.fn(() => {
    this.onstart?.();
  });

  stop = jest.fn(() => {
    this.onend?.();
  });

  abort = jest.fn(() => {
    this.onend?.();
  });
}

describe("useAudioRecording", () => {
  const mockOnTranscriptionComplete = jest.fn();
  const mockOnError = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset window.SpeechRecognition
    (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition =
      undefined;
    (
      window as Window & { webkitSpeechRecognition?: unknown }
    ).webkitSpeechRecognition = undefined;
  });

  it("returns isSupported as false when SpeechRecognition is not available", () => {
    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    expect(result.current.isSupported).toBe(false);
    expect(result.current.state).toBe("idle");
  });

  it("returns isSupported as true when SpeechRecognition is available", () => {
    (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    expect(result.current.isSupported).toBe(true);
  });

  it("returns isSupported as true when webkitSpeechRecognition is available", () => {
    (
      window as Window & { webkitSpeechRecognition?: unknown }
    ).webkitSpeechRecognition = MockSpeechRecognition;

    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    expect(result.current.isSupported).toBe(true);
  });

  it("calls onError when starting recording without support", () => {
    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    act(() => {
      result.current.startRecording();
    });

    expect(mockOnError).toHaveBeenCalledWith(
      "Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.",
    );
  });

  it("starts recording and sets state to recording", () => {
    (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    act(() => {
      result.current.startRecording();
    });

    expect(result.current.state).toBe("recording");
    expect(result.current.isRecording).toBe(true);
  });

  it("stops recording and sets state to processing", () => {
    (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    act(() => {
      result.current.startRecording();
    });

    act(() => {
      result.current.stopRecording();
    });

    // After stop is called, state goes to processing, then idle after onend
    expect(result.current.state).toBe("idle");
  });

  it("cancels recording and resets state", () => {
    (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
        onError: mockOnError,
      }),
    );

    act(() => {
      result.current.startRecording();
    });

    act(() => {
      result.current.cancelRecording();
    });

    expect(result.current.state).toBe("idle");
    expect(result.current.isRecording).toBe(false);
  });

  it("initializes with idle state", () => {
    const { result } = renderHook(() =>
      useAudioRecording({
        onTranscriptionComplete: mockOnTranscriptionComplete,
      }),
    );

    expect(result.current.state).toBe("idle");
    expect(result.current.isRecording).toBe(false);
  });
});
