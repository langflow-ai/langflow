import { useEffect, useRef, useState } from "react";
import type { UpdateMemoryParams } from "@/controllers/API/queries/memories/types";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";

type UpdateMemoryMutation = {
  mutate: (
    variables: UpdateMemoryParams,
    options?: { onSuccess?: () => void },
  ) => void;
};

type UseAutoCaptureDebouncedToggleArgs = {
  memory: MemoryInfo | undefined;
  updateMemoryMutation: UpdateMemoryMutation;
  debounceMs?: number;
};

export const useAutoCaptureDebouncedToggle = ({
  memory,
  updateMemoryMutation,
  debounceMs = 300,
}: UseAutoCaptureDebouncedToggleArgs) => {
  const autoCaptureTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const committedIsActiveRef = useRef<boolean | null>(null);

  const [autoCaptureDraft, setAutoCaptureDraft] = useState<boolean | null>(null);

  useEffect(() => {
    committedIsActiveRef.current = memory?.is_active ?? null;
  }, [memory?.is_active]);

  useEffect(() => {
    setAutoCaptureDraft(null);
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

  const handleToggleActive = (nextIsActive: boolean) => {
    if (!memory) return;
    const committedIsActive = committedIsActiveRef.current ?? memory.is_active;

    if (committedIsActive === nextIsActive) {
      if (autoCaptureTimerRef.current) {
        clearTimeout(autoCaptureTimerRef.current);
        autoCaptureTimerRef.current = null;
      }
      setAutoCaptureDraft(null);
      return;
    }

    setAutoCaptureDraft(nextIsActive);

    if (autoCaptureTimerRef.current) {
      clearTimeout(autoCaptureTimerRef.current);
      autoCaptureTimerRef.current = null;
    }

    autoCaptureTimerRef.current = setTimeout(() => {
      // If the committed value already matches, skip a no-op update.
      if ((committedIsActiveRef.current ?? memory.is_active) === nextIsActive) {
        setAutoCaptureDraft(null);
        autoCaptureTimerRef.current = null;
        return;
      }

      updateMemoryMutation.mutate(
        {
          memoryId: memory.id,
          auto_capture: nextIsActive,
        },
        {
          onSuccess: () => {
            setAutoCaptureDraft(null);
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
