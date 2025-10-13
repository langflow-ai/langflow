import Keycloak from "keycloak-js";
import type { KeycloakConfig } from "keycloak-js";

export interface KeycloakServiceConfig {
  url: string;
  realm: string;
  clientId: string;
}

class KeycloakService {
  private static instance: KeycloakService;
  private keycloak: Keycloak | null = null;
  private initialized = false;

  private constructor() {}

  public static getInstance(): KeycloakService {
    if (!KeycloakService.instance) {
      KeycloakService.instance = new KeycloakService();
    }
    return KeycloakService.instance;
  }

  public async initialize(config: KeycloakServiceConfig): Promise<boolean> {
    if (this.initialized) {
      return true;
    }

    const keycloakConfig: KeycloakConfig = {
      url: config.url,
      realm: config.realm,
      clientId: config.clientId,
    };

    this.keycloak = new Keycloak(keycloakConfig);

    try {
      const authenticated = await this.keycloak.init({
        onLoad: "check-sso",
        checkLoginIframe: false,
        pkceMethod: "S256",
      });

      this.initialized = true;
      return authenticated;
    } catch (error) {
      console.error("Failed to initialize Keycloak:", error);
      throw error;
    }
  }

  public async login(redirectUri?: string): Promise<void> {
    if (!this.keycloak) {
      throw new Error("Keycloak not initialized");
    }

    await this.keycloak.login({
      redirectUri: redirectUri || window.location.origin,
    });
  }

  public async logout(redirectUri?: string): Promise<void> {
    if (!this.keycloak) {
      throw new Error("Keycloak not initialized");
    }

    await this.keycloak.logout({
      redirectUri: redirectUri || window.location.origin,
    });
  }

  public getToken(): string | undefined {
    return this.keycloak?.token;
  }

  public getRefreshToken(): string | undefined {
    return this.keycloak?.refreshToken;
  }

  public isAuthenticated(): boolean {
    return this.keycloak?.authenticated ?? false;
  }

  public async updateToken(minValidity = 30): Promise<boolean> {
    if (!this.keycloak) {
      throw new Error("Keycloak not initialized");
    }

    try {
      return await this.keycloak.updateToken(minValidity);
    } catch (error) {
      console.error("Failed to refresh token:", error);
      throw error;
    }
  }

  public getUserInfo(): any {
    if (!this.keycloak?.tokenParsed) {
      return null;
    }

    return {
      id: this.keycloak.tokenParsed.sub,
      username: this.keycloak.tokenParsed.preferred_username,
      email: this.keycloak.tokenParsed.email,
      firstName: this.keycloak.tokenParsed.given_name,
      lastName: this.keycloak.tokenParsed.family_name,
      roles: this.keycloak.tokenParsed.realm_access?.roles || [],
    };
  }

  public hasRole(role: string): boolean {
    const userInfo = this.getUserInfo();
    return userInfo?.roles?.includes(role) ?? false;
  }

  public isTokenExpired(): boolean {
    return this.keycloak?.isTokenExpired() ?? true;
  }

  public onTokenExpired(callback: () => void): void {
    if (this.keycloak) {
      this.keycloak.onTokenExpired = callback;
    }
  }

  public onAuthSuccess(callback: () => void): void {
    if (this.keycloak) {
      this.keycloak.onAuthSuccess = callback;
    }
  }

  public onAuthError(callback: (error: any) => void): void {
    if (this.keycloak) {
      this.keycloak.onAuthError = callback;
    }
  }

  public onAuthLogout(callback: () => void): void {
    if (this.keycloak) {
      this.keycloak.onAuthLogout = callback;
    }
  }
}

export default KeycloakService;