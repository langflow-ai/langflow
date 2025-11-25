/**
 * Auth types for user roles and permissions from genesis-service-auth
 */

export interface RoleType {
  id: number;
  name: string;
}

export interface UserRole {
  id: number;
  name: string;
  roleType: RoleType;
}

export interface UserContact {
  email: string;
  phoneNumber: string | null;
  secondaryEmail: string | null;
  secondaryPhoneNumber: string | null;
}

export interface ClientStatus {
  id: number;
  clientId: number;
  expiryOn: string;
  isExpired: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Client {
  id: number;
  name: string;
  realmName: string | null;
  status: ClientStatus;
  isDeleted: boolean;
  clientType: string;
}

export interface AuthUserData {
  id: number;
  firstName: string;
  lastName: string;
  roles: UserRole[];
  entities: unknown[];
  status: number;
  lastActivationEmailSent: string | null;
  userContact: UserContact;
  client: Client;
  artifactsSpecificRoles: unknown[];
  artifactsSpecificGroupRoles: unknown[];
}

export interface AuthUserResponse {
  data: AuthUserData;
  status: number;
}

// Role name constants
export const USER_ROLES = {
  MARKETPLACE_ADMIN: "Marketplace Admin",
  AGENT_DEVELOPER: "Agent Developer",
  SUPER_ADMIN: "Super Admin",
} as const;

export type UserRoleName = (typeof USER_ROLES)[keyof typeof USER_ROLES];
