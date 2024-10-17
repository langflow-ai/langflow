export const getIconName = (
  disabled: boolean,
  selectedOption: string,
  optionsIcon: string,
) => {
  if (disabled) return "lock";
  if (selectedOption) return "GlobeOkIcon";
  return optionsIcon;
};
