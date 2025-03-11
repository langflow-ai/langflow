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
  }, [isRecording, setRecordingTime, setBarHeights]);

  useEffect(() => {
    if (!isRecording) return;

    // Use the functional update pattern to avoid dependency on barHeights
    setBarHeights((prevBarHeights) => {
      const newBarHeights = [...prevBarHeights];
      const position = 29 - (recordingTime % 30);
      newBarHeights[position] = Math.floor(Math.random() * 40) + 60;
      return newBarHeights;
    });
  }, [recordingTime, isRecording, setBarHeights]);
};
