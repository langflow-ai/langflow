export const getIconName = (
  disabled: boolean,
  selectedOption: string,
  optionsIcon: string,
  nodeStyle: boolean,
) => {
  if (disabled) return "lock";
  if (selectedOption && nodeStyle) return "GlobeOkIcon";
  return optionsIcon;
};
