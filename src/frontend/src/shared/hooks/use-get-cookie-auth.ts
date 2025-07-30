import { Cookies } from "react-cookie";

const useGetCookieAuth = (tokenName: string) => {
  const cookies = new Cookies();
  return cookies.get(tokenName);
};

export default useGetCookieAuth;
