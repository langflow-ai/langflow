import { Cookies } from "react-cookie";

const useSetCookieAuth = (tokenName: string, tokenValue: string) => {
  const cookies = new Cookies();

  cookies.set(tokenName, tokenValue, {
    path: "/",
    secure: true,
    sameSite: "strict",
  });
};

export default useSetCookieAuth;
