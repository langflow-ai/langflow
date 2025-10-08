import { Outlet } from "react-router-dom";
import { useCustomPostAuth } from "@/customization/hooks/use-custom-post-auth";

export function AppAuthenticatedPage() {
  useCustomPostAuth();

  return <Outlet />;
}
