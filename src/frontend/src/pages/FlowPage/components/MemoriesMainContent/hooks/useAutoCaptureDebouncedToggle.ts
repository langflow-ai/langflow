import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  MemoryInfo,
  UpdateMemoryParams,
} from "@/controllers/API/queries/memories/types";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { AUTO_CAPTURE_DEBOUNCE_MS } from "../MemoriesMainContent.constants";

type UpdateMemoryMutation = {
  mutate: (
    variables: UpdateMemoryParams,
    options?: { onSuccess?: () => void; onError?: (error: unknown) => void },
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
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

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

    const capturedId = memory.id;
    const capturedIsActive = memory.is_active;

    autoCaptureTimerRef.current = setTimeout(() => {
      // If the committed value already matches, skip a no-op update.
      if ((committedIsActiveRef.current ?? capturedIsActive) === nextIsActive) {
        setAutoCaptureDraft(null);
        draftIsActiveRef.current = null;
        autoCaptureTimerRef.current = null;
        return;
      }

      const clearDraft = () => {
        setAutoCaptureDraft(null);
        draftIsActiveRef.current = null;
      };

      const currentName = memory?.name ?? capturedId;

      updateMemoryMutation.mutate(
        {
          memoryId: capturedId,
          auto_capture: nextIsActive,
        },
        {
          onSuccess: () => {
            clearDraft();
            setSuccessData({
              title: nextIsActive
                ? t("memory.autoCaptureEnabledFor", { name: currentName })
                : t("memory.autoCaptureDisabledFor", { name: currentName }),
            });
          },
          onError: (error: unknown) => {
            clearDraft();
            setErrorData({
              title: t("memory.autoCaptureError"),
              list: extractApiErrorMessages(error),
            });
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
