import { useEffect, useState } from "react";

interface ProgressBarProps {
  remSize?: number;
}

export function ProgressBar({ remSize = 16 }: ProgressBarProps) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const intervals = [
      { target: 60, duration: 3000 },
      { target: 85, duration: 3000 },
      { target: 95, duration: 4000 },
    ];

    let currentProgress = 0;
    let currentPhase = 0;
    let phaseStartProgress = 0;
    let phaseStartTime = Date.now();

    const timer = setInterval(() => {
      if (currentPhase >= intervals.length) {
        clearInterval(timer);
        return;
      }

      const phase = intervals[currentPhase];
      const elapsed = Date.now() - phaseStartTime;
      const phaseProgress = Math.min(elapsed / phase.duration, 1);
      const easedProgress = 1 - Math.pow(1 - phaseProgress, 3);

      currentProgress =
        phaseStartProgress +
        (phase.target - phaseStartProgress) * easedProgress;
      setProgress(currentProgress);

      if (phaseProgress >= 1) {
        currentPhase++;
        phaseStartProgress = phase.target;
        phaseStartTime = Date.now();
      }
    }, 16);

    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ width: `${remSize}rem` }}>
      <div className="loading-progress-shell">
        <div className="loading-progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

export default ProgressBar;