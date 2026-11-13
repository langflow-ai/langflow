// Keyboard focus stays visible; a mouse pick no longer leaves a ring that the dialog clips.
export const QUIET_SELECT_TRIGGER =
  "focus-visible:ring-1 focus-visible:ring-offset-0";

// The shared dialog focuses its own container on open (so focus enters it without landing on the close
// button); that container is not a control, so it gets no outline. Fields inside keep their focus rings.
export const DIALOG_CONTAINER =
  "outline-none focus:outline-none focus-visible:outline-none";
