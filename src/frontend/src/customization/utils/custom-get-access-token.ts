import { Cookies } from "react-cookie";
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";

export const customGetAccessToken = () => {
  const cookies = new Cookies();
  return cookies.get(LANGFLOW_ACCESS_TOKEN);
};
