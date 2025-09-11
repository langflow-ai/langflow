import {
  DEFAULT_PLACEHOLDER,
  RECEIVING_INPUT_VALUE,
} from "@/constants/constants";

export const getPlaceholder = (
  disabled: boolean,
  returnMessage: string = DEFAULT_PLACEHOLDER,
) => {
  if (disabled) return RECEIVING_INPUT_VALUE;

  return returnMessage || DEFAULT_PLACEHOLDER;
};
