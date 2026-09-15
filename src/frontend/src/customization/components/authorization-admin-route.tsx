import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useGetAuthorizationCapabilities } from "@/controllers/API/queries/authorization";

export function AuthorizationAdminRoute({
  children,
  requiresCollaboration = true,
}: {
  children: ReactNode;
  requiresCollaboration?: boolean;
}) {
  const { t } = useTranslation();
  const capabilities = useGetAuthorizationCapabilities();
  if (capabilities.isLoading)
    return (
      <p role="status" className="p-6">
        {t("authz.guard.loading")}
      </p>
    );
  if (
    capabilities.isError ||
    !capabilities.data ||
    (requiresCollaboration &&
      (!capabilities.data.enforcement_active ||
        !capabilities.data.service_ready))
  ) {
    return (
      <Alert variant="destructive" className="m-6">
        <AlertDescription>{t("authz.guard.unavailable")}</AlertDescription>
      </Alert>
    );
  }
  if (!capabilities.data.can_administer_platform)
    return <Navigate replace to="/teams" />;
  return children;
}
