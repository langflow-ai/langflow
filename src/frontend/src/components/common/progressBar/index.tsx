import { useEffect, useState } from "react";

interface ProgressBarProps {
  remSize?: number;
}

export function ProgressBar({ remSize = 16 }: ProgressBarProps) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Smart adaptive progress: fast at start, dramatically slower at end
    // 0-60% in 3s (fast)
    // 60-85% in 3s (medium)
    // 85-95% in 4s (very slow)
    // Total: ~10 seconds to reach 95%

    const intervals = [
      { target: 60, duration: 3000 }, // Quick start
      { target: 85, duration: 3000 }, // Slow down
      { target: 95, duration: 4000 }, // Crawl to finish
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

      // Easing function for smooth deceleration
      const easedProgress = 1 - Math.pow(1 - phaseProgress, 3);

      currentProgress =
        phaseStartProgress +
        (phase.target - phaseStartProgress) * easedProgress;
      setProgress(currentProgress);

      // Move to next phase when current phase completes
      if (phaseProgress >= 1) {
        currentPhase++;
        phaseStartProgress = phase.target;
        phaseStartTime = Date.now();
      }
    }, 16); // ~60fps for smooth animation

    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ width: `${remSize}rem` }}>
      {/* Progress bar container */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-border">
        {/* Progress bar fill */}
        <div
          className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
