export type StatusIconProps = {
  colorClass: string;
  iconName: "Loader2" | "CircleCheck" | "CircleX";
  shouldSpin: boolean;
};

export const getStatusIconProps = (
  status: string | null | undefined,
): StatusIconProps => {
  const normalized = status ?? "";
  const isSuccess = normalized === "success";
  const isError = normalized === "error";
  const isRunning = normalized === "running";

  return {
    colorClass: isError
      ? "text-status-red"
      : isSuccess
        ? "text-status-green"
        : "text-muted-foreground",
    iconName: isRunning ? "Loader2" : isSuccess ? "CircleCheck" : "CircleX",
    shouldSpin: isRunning,
  };
};
