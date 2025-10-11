import { Cookies } from "react-cookie";
import { AI_STUDIO_ACCESS_TOKEN } from "@/constants/constants";

export const customGetAccessToken = () => {
  const cookies = new Cookies();
  return cookies.get(AI_STUDIO_ACCESS_TOKEN);
};
