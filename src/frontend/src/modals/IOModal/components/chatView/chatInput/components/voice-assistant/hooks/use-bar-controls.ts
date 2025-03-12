import { useEffect, useRef } from "react";

export const useBarControls = (
  isRecording: boolean,
  setRecordingTime: React.Dispatch<React.SetStateAction<number>>,
  barHeights: number[],
  setBarHeights: React.Dispatch<React.SetStateAction<number[]>>,
  recordingTime: number,
  analyserRef?: React.MutableRefObject<AnalyserNode | null>,
  setSoundDetected?: React.Dispatch<React.SetStateAction<boolean>>,
) => {
  const animationFrameRef = useRef<number | null>(null);
  const timeDataRef = useRef<Uint8Array | null>(null);

  // Timer effect for recording time
  useEffect(() => {
    if (isRecording) {
      const interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setBarHeights(Array(30).fill(20));
      if (setSoundDetected) setSoundDetected(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }
  }, [isRecording, setRecordingTime, setBarHeights, setSoundDetected]);

  // Set initial bar heights with a static pattern
  useEffect(() => {
    // Create a static pattern for the bars
    const staticHeights = Array(30)
      .fill(0)
      .map((_, i) => {
        // Create a slight curve pattern for visual interest
        const position = i / 30;
        const centerDistance = Math.abs(position - 0.5);
        const height = 50 + Math.sin(position * Math.PI) * 30;
        return Math.max(20, Math.min(80, height));
      });

    setBarHeights(staticHeights);
  }, [setBarHeights]);

  // Sound detection effect without height animation
  useEffect(() => {
    if (!isRecording) return;

    // Initialize time domain data array for sound detection
    if (analyserRef?.current) {
      const analyser = analyserRef.current;
      analyser.fftSize = 256;

      if (
        !timeDataRef.current ||
        timeDataRef.current.length !== analyser.fftSize
      ) {
        timeDataRef.current = new Uint8Array(analyser.fftSize);
      }
    }

    // Create animation function that only detects sound
    const animate = () => {
      let soundDetected = false;

      // Try to detect sound from microphone
      if (analyserRef?.current && timeDataRef.current) {
        try {
          const analyser = analyserRef.current;

          // Get time domain data
          analyser.getByteTimeDomainData(timeDataRef.current);

          // Calculate volume level
          let sum = 0;
          let max = 0;
          for (let i = 0; i < timeDataRef.current.length; i++) {
            // Deviation from 128 (silence in time domain)
            const deviation = Math.abs(timeDataRef.current[i] - 128);
            sum += deviation;
            max = Math.max(max, deviation);
          }

          // Calculate volume level (0-1 range) using both average and max
          const volumeLevel =
            (sum / (timeDataRef.current.length * 128)) * 0.5 +
            (max / 128) * 0.5;

          // Scale up for better detection
          const scaledVolume = volumeLevel * 10;

          // Detect sound when volume is above threshold
          soundDetected = scaledVolume > 0.1;

          // Update sound detection state if provided
          if (setSoundDetected) {
            setSoundDetected(soundDetected);
          }
        } catch (error) {
          console.error("Error detecting sound:", error);
        }
      } else {
        // Fallback for sound detection in case no analyser is available
        if (setSoundDetected) {
          setSoundDetected(false);
        }
      }

      // Continue animation
      animationFrameRef.current = requestAnimationFrame(animate);
    };

    // Start animation
    animationFrameRef.current = requestAnimationFrame(animate);

    // Cleanup on unmount or when recording stops
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isRecording, analyserRef, setSoundDetected]);
};
