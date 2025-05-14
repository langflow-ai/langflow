import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { Cookies } from "react-cookie";

export const customGetAccessToken = () => {
  const cookies = new Cookies();
  return cookies.get(LANGFLOW_ACCESS_TOKEN);
};
