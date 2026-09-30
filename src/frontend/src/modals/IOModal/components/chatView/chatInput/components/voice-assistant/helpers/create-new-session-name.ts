export const createNewSessionName = () => {
  return `Session ${new Date().toLocaleString("en-US", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    second: "2-digit",
    timeZone: "UTC",
  })}`;
};
