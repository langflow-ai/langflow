export const CONTAINER_VARIANTS = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
};

export const STOP_BUTTON_VARIANTS = {
  hidden: { opacity: 0, x: 0 },
  visible: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 0 },
};

export const RETRY_BUTTON_VARIANTS = {
  hidden: { opacity: 0, x: 10 },
  visible: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 10 },
};

export const DISMISS_BUTTON_VARIANTS = {
  hidden: { opacity: 0, x: 10 },
  visible: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 10 },
};

export const TIME_VARIANTS = {
  single: { x: -75, width: "auto" },
  double: { x: -165, width: "auto" },
  none: { x: 0, width: "auto" },
};
