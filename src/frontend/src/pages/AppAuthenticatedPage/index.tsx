import { Outlet } from "react-router-dom";
import { useCustomPostAuth } from "@/customization/hooks/use-custom-post-auth";
import { useUserRoles } from "@/hooks/useUserRoles";

export function AppAuthenticatedPage() {
  useCustomPostAuth();
  useUserRoles(); // Fetch user roles on app init for role-based access control

  return <Outlet />;
}
