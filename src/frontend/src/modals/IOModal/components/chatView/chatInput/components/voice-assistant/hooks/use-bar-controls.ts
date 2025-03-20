import { useEffect, useRef } from "react";

export const useBarControls = (
  isRecording: boolean,
  setRecordingTime: React.Dispatch<React.SetStateAction<number>>,
  setBarHeights: React.Dispatch<React.SetStateAction<number[]>>,
  analyserRef?: React.MutableRefObject<AnalyserNode | null>,
  setSoundDetected?,
) => {
  const animationFrameRef = useRef<number | null>(null);
  const timeDataRef = useRef<Uint8Array | null>(null);
  const baseHeightsRef = useRef<number[]>([]);
  const lastRandomizeTimeRef = useRef<number>(0);
  const minHeightRef = useRef<number>(20);
  const analyzerInitializedRef = useRef<boolean>(false);

  useEffect(() => {
    if (isRecording) {
      analyzerInitializedRef.current = false;

      if (analyserRef?.current) {
        const analyser = analyserRef.current;
        analyser.fftSize = 256;
        timeDataRef.current = new Uint8Array(analyser.fftSize);
        analyzerInitializedRef.current = true;
      }

      const interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setBarHeights(Array(30).fill(minHeightRef.current));
      if (setSoundDetected) setSoundDetected(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      timeDataRef.current = null;
    }
  }, [
    isRecording,
    setRecordingTime,
    setBarHeights,
    setSoundDetected,
    analyserRef,
  ]);

  useEffect(() => {
    const staticHeights = Array(30)
      .fill(0)
      .map((_, i) => {
        const position = i / 30;
        const height = 50 + Math.sin(position * Math.PI) * 30;
        return Math.max(minHeightRef.current, Math.min(80, height));
      });

    setBarHeights(staticHeights);
    baseHeightsRef.current = staticHeights;
  }, [setBarHeights]);

  useEffect(() => {
    if (
      analyserRef?.current &&
      !analyzerInitializedRef.current &&
      isRecording
    ) {
      const analyser = analyserRef.current;
      analyser.fftSize = 256;
      timeDataRef.current = new Uint8Array(analyser.fftSize);
      analyzerInitializedRef.current = true;
    }
  }, [analyserRef?.current, isRecording]);

  useEffect(() => {
    if (!isRecording) return;

    if (
      analyserRef?.current &&
      (!timeDataRef.current || !analyzerInitializedRef.current)
    ) {
      const analyser = analyserRef.current;
      analyser.fftSize = 256;
      timeDataRef.current = new Uint8Array(analyser.fftSize);
      analyzerInitializedRef.current = true;
    }

    const animate = (timestamp: number) => {
      let soundDetected = false;
      let scaledVolume = 0;

      if (analyserRef?.current && timeDataRef.current) {
        try {
          const analyser = analyserRef.current;

          if (timeDataRef.current.length !== analyser.fftSize) {
            timeDataRef.current = new Uint8Array(analyser.fftSize);
          }

          analyser.getByteTimeDomainData(timeDataRef.current);

          let sum = 0;
          let max = 0;
          for (let i = 0; i < timeDataRef.current.length; i++) {
            const deviation = Math.abs(timeDataRef.current[i] - 128);
            sum += deviation;
            max = Math.max(max, deviation);
          }

          const volumeLevel =
            (sum / (timeDataRef.current.length * 128)) * 0.5 +
            (max / 128) * 0.5;

          scaledVolume = volumeLevel * 10;

          soundDetected = scaledVolume > 0.3;

          if (setSoundDetected) {
            setSoundDetected(soundDetected);
          }
        } catch (error) {
          console.error("Error detecting sound:", error);
          if (setSoundDetected) {
            setSoundDetected(false);
          }
        }
      } else {
        if (setSoundDetected) {
          setSoundDetected(false);
        }
      }

      const shouldRandomize =
        soundDetected && timestamp - lastRandomizeTimeRef.current > 100;

      if (shouldRandomize) {
        lastRandomizeTimeRef.current = timestamp;
      }

      setBarHeights((prevHeights) => {
        return prevHeights.map((height, index) => {
          if (soundDetected) {
            const baseHeight = baseHeightsRef.current[index] || 50;

            const volumeFactor = 1.0 + Math.min(1.5, scaledVolume);

            const randomFactor = shouldRandomize
              ? 0.7 + Math.random() * 0.6
              : 0.85 + Math.random() * 0.3;

            const newHeight = baseHeight * volumeFactor * randomFactor;

            return Math.max(minHeightRef.current, Math.min(120, newHeight));
          } else {
            return height + (minHeightRef.current - height) * 0.2;
          }
        });
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isRecording, analyserRef, setSoundDetected, setBarHeights]);
};
