export const getTestId = (
  type: string,
  index: number,
  editNode: boolean,
  componentName: string,
) =>
  `input-list-${type}-btn${editNode ? "-edit" : ""}_${componentName}-${index}`;
