import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";

export interface TriggersListStateProps {
  query: Pick<UseQueryResult<unknown>, "isLoading" | "isError" | "error">;
  total: number;
  visible: number;
  emptyKey: string;
  children: ReactNode;
}

/** Loading, error, empty and no-match states around a triggers table. */
export function TriggersListState({
  query,
  total,
  visible,
  emptyKey,
  children,
}: TriggersListStateProps) {
  const { t } = useTranslation();
  if (query.isLoading) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        {t("triggers.loading")}
      </p>
    );
  }
  if (query.isError) {
    return (
      <p className="text-sm text-destructive" role="alert">
        {getAxiosErrorDetail(query.error, t("triggers.errors.load"))}
      </p>
    );
  }
  if (total === 0 || visible === 0) {
    return (
      <div
        className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground"
        data-testid="triggers-empty"
      >
        {total === 0 ? t(emptyKey) : t("triggers.empty.noMatch")}
      </div>
    );
  }
  return <>{children}</>;
}

export default TriggersListState;
