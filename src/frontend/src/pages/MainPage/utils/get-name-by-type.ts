export const getNameByType = (type: string) => {
  switch (type) {
    case "all":
      return "Component or Flow";
    case "component":
      return "Component";
    default:
      return "Flow";
  }
};
