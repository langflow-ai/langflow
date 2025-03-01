export const track = async (
  name: string,
  properties: Record<string, any> = {},
  id: string = "",
): Promise<void> => {
  return;
};

export const trackFlowBuild = async (
  flowName: string,
  isError?: boolean,
  properties?: Record<string, any>,
): Promise<void> => {
  return;
};

export const trackDataLoaded = async (
  flowId?: string,
  flowName?: string,
  component?: string,
  componentId?: string,
): Promise<void> => {
  return;
};
