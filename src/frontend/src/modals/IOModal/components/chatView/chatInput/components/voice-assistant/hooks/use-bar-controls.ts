import { useEffect } from "react";

export const useBarControls = (
  isRecording: boolean,
  setRecordingTime: React.Dispatch<React.SetStateAction<number>>,
  barHeights: number[],
  setBarHeights: React.Dispatch<React.SetStateAction<number[]>>,
  recordingTime: number,
) => {
  useEffect(() => {
    if (isRecording) {
      const interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setBarHeights(Array(30).fill(20));
    }
  }, [isRecording]);

  useEffect(() => {
    if (!isRecording) return;
    const newBarHeights = [...barHeights];
    const position = 29 - (recordingTime % 30);
    newBarHeights[position] = Math.floor(Math.random() * 40) + 60;
    setBarHeights(newBarHeights);
  }, [recordingTime, isRecording, barHeights]);
};
