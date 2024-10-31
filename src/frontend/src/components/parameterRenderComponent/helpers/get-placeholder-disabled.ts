import { RECEIVING_INPUT_VALUE } from "@/constants/constants";

export const getPlaceholder = (disabled: boolean, returnMessage: string) => {
  if (disabled) return RECEIVING_INPUT_VALUE;
  return returnMessage;
};
