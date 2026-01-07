import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { cookieManager } from "@/utils/cookie-manager";

export const customGetAccessToken = () => {
  return cookieManager.get(LANGFLOW_ACCESS_TOKEN);
};
