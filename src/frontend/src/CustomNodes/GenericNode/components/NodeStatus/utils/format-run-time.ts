export function normalizeTimeString(input) {
  if (!input) return null;
  // Remove any whitespace and convert to lowercase
  const cleanInput = input?.toLowerCase()?.replace(/\s+/g, "");

  // Different patterns to match
  const patterns = {
    // 1.15 seconds or 1.15seconds
    seconds: /^(\d*\.?\d+)seconds?$/,
    // 14ms or 14 ms
    milliseconds: /^(\d+)ms$/,
    // 1minute, 1.21 seconds or similar variations
    minuteSeconds: /^(\d+)minutes?,(\d*\.?\d+)seconds?$/,
  };

  // Check for seconds
  if (patterns.seconds.test(cleanInput)) {
    const [, seconds] = cleanInput.match(patterns.seconds);
    return `${parseFloat(seconds)}s`;
  }

  // Check for milliseconds
  if (patterns.milliseconds.test(cleanInput)) {
    const [, ms] = cleanInput.match(patterns.milliseconds);
    return `${ms}ms`;
  }

  // Check for minute and seconds combination
  if (patterns.minuteSeconds.test(cleanInput)) {
    const [, minutes, seconds] = cleanInput.match(patterns.minuteSeconds);
    return `${parseFloat(minutes)}.${Math.round((parseFloat(seconds) * 100) / 60)}m`;
  }

  // Return null or throw error if no pattern matches
  return null;
}
