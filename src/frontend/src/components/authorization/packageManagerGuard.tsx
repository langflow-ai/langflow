import { Navigate } from "react-router-dom";
import { useUtilityStore } from "@/stores/utilityStore";

interface PackageManagerGuardProps {
  children: React.ReactNode;
}

export function PackageManagerGuard({ children }: PackageManagerGuardProps) {
  const packageManagerEnabled = useUtilityStore(
    (state) => state.packageManagerEnabled,
  );

  if (!packageManagerEnabled) {
    return <Navigate to="/settings" replace />;
  }

  return <>{children}</>;
}
