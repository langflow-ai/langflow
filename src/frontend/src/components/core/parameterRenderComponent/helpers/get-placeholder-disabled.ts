import i18n from "../../../../i18n";

export const getPlaceholder = (
  disabled: boolean,
  returnMessage: string = i18n.t("input.placeholder"),
) => {
  if (disabled) return i18n.t("component.receivingInput");

  return returnMessage || i18n.t("input.placeholder");
};
