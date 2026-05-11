import { useCallback, useState } from "react";
import { useErrorAlert } from "./use-error-alert";

interface DeleteWithConfirmation<T extends { id: string; name: string }> {
  target: T | null;
  deletingId: string | null;
  requestDelete: (item: T) => void;
  confirmDelete: (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
  setModalOpen: (open: boolean) => void;
}

export function useDeleteWithConfirmation<
  T extends { id: string; name: string },
  P,
>(
  mutateFn: (
    vars: P,
    opts: { onError: (err: unknown) => void; onSettled: () => void },
  ) => void,
  buildParams: (id: string) => P,
  errorMessage: string,
): DeleteWithConfirmation<T> {
  const [target, setTarget] = useState<T | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const showError = useErrorAlert();

  const requestDelete = useCallback((item: T) => {
    setTarget(item);
  }, []);

  const confirmDelete = useCallback(
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
      e.stopPropagation();
      if (!target) return;
      const current = target;
      setDeletingId(current.id);
      setTarget(null);
      mutateFn(buildParams(current.id), {
        onError: (error: unknown) => {
          showError(errorMessage, error);
        },
        onSettled: () => setDeletingId(null),
      });
    },
    [target, mutateFn, buildParams, errorMessage, showError],
  );

  const setModalOpen = useCallback((open: boolean) => {
    if (!open) setTarget(null);
  }, []);

  return {
    target,
    deletingId,
    requestDelete,
    confirmDelete,
    setModalOpen,
  };
}
