import { Cookies } from "react-cookie";

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
    this.cookies.set(name, value, {
      path: "/",
      secure: true,
      sameSite: "strict",
      ...options,
    });
  }

  public remove(name: string, options?: { path?: string }): void {
    this.cookies.remove(name, { path: "/", ...options });
  }
}

export const cookieManager = CookieManager.getInstance();
export const getCookiesInstance = () => cookieManager.getCookies();
