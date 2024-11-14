export const getIconName = (
  disabled?: boolean,
  selectedOption?: string,
  optionsIcon?: string,
  nodeStyle?: boolean,
  isToolMode?: boolean,
) => {
  if (isToolMode) return "Hammer";
  if (disabled) return "lock";
  if (selectedOption && nodeStyle) return "GlobeOkIcon";
  return optionsIcon;
};
