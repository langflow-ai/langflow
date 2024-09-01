import {
  getCurlRunCode,
  getCurlWebhookCode,
} from "@/modals/apiModal/utils/get-curl-code";
import getJsApiCode from "@/modals/apiModal/utils/get-js-api-code";
import getPythonApiCode from "@/modals/apiModal/utils/get-python-api-code";
import getPythonCode from "@/modals/apiModal/utils/get-python-code";
import getWidgetCode from "@/modals/apiModal/utils/get-widget-code";

export function useCustomAPICode() {
  return {
    getCurlRunCode,
    getCurlWebhookCode,
    getJsApiCode,
    getPythonApiCode,
    getPythonCode,
    getWidgetCode,
  };
}
