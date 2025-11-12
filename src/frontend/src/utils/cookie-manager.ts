import { Cookies } from "react-cookie";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";

class CookieManager {
  private static instance: CookieManager;
  private cookies: Cookies;

  private constructor() {
    this.cookies = new Cookies();
  }

  public static getInstance(): CookieManager {
    if (!CookieManager.instance) {
      CookieManager.instance = new CookieManager();
    }
    return CookieManager.instance;
  }

  public getCookies(): Cookies {
    return this.cookies;
  }

  public get(name: string): string | undefined {
    return this.cookies.get(name);
  }

  public set(
    name: string,
    value: string,
    options?: {
      path?: string;
      secure?: boolean;
      sameSite?: "strict" | "lax" | "none";
      expires?: Date;
      domain?: string;
    },
  ): void {
    // Only use secure flag if the connection is HTTPS
    const isSecure =
      typeof window !== "undefined" && window.location.protocol === "https:";

    this.cookies.set(name, value, {
      path: "/",
      secure: isSecure,
      sameSite: isSecure ? "strict" : "lax",
      ...options,
    });
  }

  public remove(
    name: string,
    options?: { path?: string; domain?: string },
  ): void {
    // Use the same options that were used when setting the cookie
    const isSecure =
      typeof window !== "undefined" && window.location.protocol === "https:";

    this.cookies.remove(name, {
      path: "/",
      secure: isSecure,
      sameSite: isSecure ? "strict" : "lax",
      ...options,
    });
  }

  public clearAuthCookies(): void {
    this.remove(LANGFLOW_ACCESS_TOKEN);
    this.remove(LANGFLOW_API_TOKEN);
    this.remove(LANGFLOW_REFRESH_TOKEN);
    this.remove(LANGFLOW_AUTO_LOGIN_OPTION);
  }
}

export const cookieManager = CookieManager.getInstance();
export const getCookiesInstance = () => cookieManager.getCookies();
