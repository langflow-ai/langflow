import { useCallback, useState } from "react";

const DEFAULT_RESET_DELAY_MS = 1000;

export const useCopyToClipboard = ({
  resetDelay = DEFAULT_RESET_DELAY_MS,
}: { resetDelay?: number } = {}) => {
  const [isCopied, setIsCopied] = useState(false);

  const copy = useCallback(
    (payload: string) => {
      navigator.clipboard?.writeText(payload).then(
        () => {
          setIsCopied(true);
          setTimeout(() => setIsCopied(false), resetDelay);
        },
        () => {},
      );
    },
    [resetDelay],
  );

  return { copy, isCopied };
};
