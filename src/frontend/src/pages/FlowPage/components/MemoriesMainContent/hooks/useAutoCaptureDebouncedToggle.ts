import { useEffect, useRef, useState } from "react";
import type { UpdateMemoryParams } from "@/controllers/API/queries/memories/types";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import { AUTO_CAPTURE_DEBOUNCE_MS } from "../MemoriesMainContent.constants";

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

type NextIsActive = boolean | ((prevIsActive: boolean) => boolean);

export const useAutoCaptureDebouncedToggle = ({
  memory,
  updateMemoryMutation,
  debounceMs = AUTO_CAPTURE_DEBOUNCE_MS,
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

      updateMemoryMutation.mutate(
        {
          memoryId: memory.id,
          auto_capture: nextIsActive,
        },
        {
          onSuccess: () => {
            setAutoCaptureDraft(null);
            draftIsActiveRef.current = null;
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
