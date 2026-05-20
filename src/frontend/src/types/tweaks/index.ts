export type GetCodesType = {
  getCurlRunCode?: (GetCodeType) => string;
  getCurlWebhookCode?: (GetCodeType) => string;
  getJsApiCode?: (GetCodeType) => string;
  getPythonApiCode?: (GetCodeType) => string;
  getPythonCode?: (GetCodeType) => string;
  getWidgetCode?: (GetCodeType) => string;
};

export type GetCodeType = {
  flowId: string;
  flowName: string;
  isAuth?: boolean;
  webhookAuthEnable: boolean;
  tweaksBuildedObject?: {};
  endpointName?: string | null;
  activeTweaks?: boolean;
  copy?: boolean;
};
