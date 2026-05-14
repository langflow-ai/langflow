import { useEffect, useRef, useState } from "react";
import { AUTO_CAPTURE_DEBOUNCE_MS } from "../MemoriesMainContent.constants";
import type {
  MemoryInfo,
  UpdateMemoryParams,
} from "@/controllers/API/queries/memories/types";

type UpdateMemoryMutation = {
  mutate: (
    variables: UpdateMemoryParams,
    options?: { onSuccess?: () => void; onError?: () => void },
  ) => void;
};

type UseAutoCaptureDebouncedToggleArgs = {
  memory: MemoryInfo | undefined;
  updateMemoryMutation: UpdateMemoryMutation;
  debounceMs?: number;
  /**
   * Fires when the debounced auto-capture mutation actually resolves so
   * the caller can announce the state change (e.g. push a toast). Not
   * called for collapsed no-op toggles (rapid on→off→on within the
   * debounce window).
   */
  onToggleSuccess?: (nextIsActive: boolean) => void;
  onToggleError?: (nextIsActive: boolean) => void;
};

type NextIsActive = boolean | ((prevIsActive: boolean) => boolean);

export const useAutoCaptureDebouncedToggle = ({
  memory,
  updateMemoryMutation,
  debounceMs = AUTO_CAPTURE_DEBOUNCE_MS,
  onToggleSuccess,
  onToggleError,
}: UseAutoCaptureDebouncedToggleArgs) => {
  const autoCaptureTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const committedIsActiveRef = useRef<boolean | null>(null);
  const draftIsActiveRef = useRef<boolean | null>(null);

  const [autoCaptureDraft, setAutoCaptureDraft] = useState<boolean | null>(
    null,
  );

  useEffect(() => {
    draftIsActiveRef.current = autoCaptureDraft;
  }, [autoCaptureDraft]);

  useEffect(() => {
    committedIsActiveRef.current = memory?.is_active ?? null;
  }, [memory?.is_active]);

  useEffect(() => {
    setAutoCaptureDraft(null);
    draftIsActiveRef.current = null;
    committedIsActiveRef.current = null;

    if (autoCaptureTimerRef.current) {
      clearTimeout(autoCaptureTimerRef.current);
      autoCaptureTimerRef.current = null;
    }
  }, [memory?.id]);

  useEffect(() => {
    return () => {
      if (autoCaptureTimerRef.current) {
        clearTimeout(autoCaptureTimerRef.current);
        autoCaptureTimerRef.current = null;
      }
    };
  }, []);

  const handleToggleActive = (nextIsActiveOrUpdater: NextIsActive) => {
    if (!memory) return;
    const committedIsActive = committedIsActiveRef.current ?? memory.is_active;
    const currentIsActive = draftIsActiveRef.current ?? committedIsActive;
    const nextIsActive =
      typeof nextIsActiveOrUpdater === "function"
        ? nextIsActiveOrUpdater(currentIsActive)
        : nextIsActiveOrUpdater;

    if (nextIsActive === currentIsActive) return;

    if (committedIsActive === nextIsActive) {
      if (autoCaptureTimerRef.current) {
        clearTimeout(autoCaptureTimerRef.current);
        autoCaptureTimerRef.current = null;
      }
      setAutoCaptureDraft(null);
      draftIsActiveRef.current = null;
      return;
    }

    draftIsActiveRef.current = nextIsActive;
    setAutoCaptureDraft(nextIsActive);

    if (autoCaptureTimerRef.current) {
      clearTimeout(autoCaptureTimerRef.current);
      autoCaptureTimerRef.current = null;
    }

    autoCaptureTimerRef.current = setTimeout(() => {
      // If the committed value already matches, skip a no-op update.
      if ((committedIsActiveRef.current ?? memory.is_active) === nextIsActive) {
        setAutoCaptureDraft(null);
        draftIsActiveRef.current = null;
        autoCaptureTimerRef.current = null;
        return;
      }

      const clearDraft = () => {
        setAutoCaptureDraft(null);
        draftIsActiveRef.current = null;
      };

      updateMemoryMutation.mutate(
        {
          memoryId: memory.id,
          auto_capture: nextIsActive,
        },
        {
          onSuccess: () => {
            clearDraft();
            onToggleSuccess?.(nextIsActive);
          },
          // On failure the draft never resolved — reset so UI reflects server state.
          onError: () => {
            clearDraft();
            onToggleError?.(nextIsActive);
          },
        },
      );
      autoCaptureTimerRef.current = null;
    }, debounceMs);
  };

  return {
    autoCaptureDraft,
    handleToggleActive,
  };
};
