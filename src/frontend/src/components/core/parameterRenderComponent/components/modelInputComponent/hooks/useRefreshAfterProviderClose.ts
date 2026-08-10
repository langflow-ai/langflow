import { useCallback, useEffect, useRef, useState } from "react";

export interface UseRefreshAfterProviderCloseParams {
  isFetchingProviders: boolean;
  isFetchingEnabledModels: boolean;
  /** Stable setter for the manage-providers dialog (owned by the component). */
  setOpenManageProvidersDialog: (open: boolean) => void;
}

export interface UseRefreshAfterProviderCloseResult {
  isRefreshingAfterClose: boolean;
  handleManageProvidersDialogClose: (opts?: { hasChanges?: boolean }) => void;
}

/**
 * Keeps the input in a loading state after the manage-providers dialog closes
 * with changes, until a provider/enabled-models refetch has started AND settled
 * (or a 5s safety timeout fires). Extracted verbatim from ModelInputComponent
 * (LE-1736 W25).
 */
export function useRefreshAfterProviderClose({
  isFetchingProviders,
  isFetchingEnabledModels,
  setOpenManageProvidersDialog,
}: UseRefreshAfterProviderCloseParams): UseRefreshAfterProviderCloseResult {
  const [isRefreshingAfterClose, setIsRefreshingAfterClose] = useState(false);

  const handleManageProvidersDialogClose = useCallback(
    (opts?: { hasChanges?: boolean }) => {
      setOpenManageProvidersDialog(false);
      if (opts?.hasChanges) {
        setIsRefreshingAfterClose(true);
      }
    },
    [setOpenManageProvidersDialog],
  );

  const hasSeenFetchStartRef = useRef(false);
  useEffect(() => {
    if (!isRefreshingAfterClose) {
      hasSeenFetchStartRef.current = false;
      return;
    }
    if (isFetchingProviders || isFetchingEnabledModels) {
      hasSeenFetchStartRef.current = true;
    } else if (hasSeenFetchStartRef.current) {
      setIsRefreshingAfterClose(false);
    }
  }, [isRefreshingAfterClose, isFetchingProviders, isFetchingEnabledModels]);

  useEffect(() => {
    if (!isRefreshingAfterClose) return;
    const timeout = setTimeout(() => setIsRefreshingAfterClose(false), 5000);
    return () => clearTimeout(timeout);
  }, [isRefreshingAfterClose]);

  return { isRefreshingAfterClose, handleManageProvidersDialogClose };
}
