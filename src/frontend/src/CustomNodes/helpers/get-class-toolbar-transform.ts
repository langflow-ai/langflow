export const getTransformClasses = (showToolbar, showNode) => {
  if (showToolbar && showNode) return "translate-x-[10.4rem] opacity-100";
  if (!showToolbar && showNode) return "translate-x-[8rem] opacity-0";
  if (showToolbar && !showNode) return "translate-x-[6.4rem] opacity-100";
  return "translate-x-[5rem] opacity-0";
};
