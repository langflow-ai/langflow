type SaveBeforeLeavingOptions = {
  saveFlow: () => Promise<void>;
  autoSaving: boolean;
  proceed: () => void;
  reset: () => void;
  onSaved: () => void;
  autoSaveDelay?: number;
};

export async function saveBeforeLeaving({
  saveFlow,
  autoSaving,
  proceed,
  reset,
  onSaved,
  autoSaveDelay = 1200,
}: SaveBeforeLeavingOptions): Promise<void> {
  let saveFinished = false;
  let delayFinished = false;

  const timeoutId = setTimeout(() => {
    delayFinished = true;
    if (saveFinished) {
      proceed();
      onSaved();
    }
  }, autoSaveDelay);

  try {
    await saveFlow();
    saveFinished = true;

    if (!autoSaving || delayFinished) {
      clearTimeout(timeoutId);
      proceed();
      onSaved();
    }
  } catch {
    // useSaveFlow already displays its localized error with the backend detail.
    // Autosave has no manual exit choice, so release that route blocker. A
    // failed explicit "Save and Exit" returns to the editor instead of
    // discarding the user's changes without consent.
    clearTimeout(timeoutId);
    if (autoSaving) {
      proceed();
    } else {
      reset();
    }
  }
}
