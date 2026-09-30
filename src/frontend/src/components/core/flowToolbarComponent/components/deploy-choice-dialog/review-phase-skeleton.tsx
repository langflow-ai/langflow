import { useTranslation } from "react-i18next";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";

export default function ReviewPhaseSkeletonContent() {
  const { t } = useTranslation();

  return (
    <>
      <DialogHeader className="gap-2">
        <DialogTitle className="text-xl font-semibold">
          {t("deployments.updateDeployment")}
        </DialogTitle>
        <DialogDescription className="text-sm leading-5">
          {t("deployments.updateDeploymentDescription")}
        </DialogDescription>
      </DialogHeader>

      <div
        className="flex min-h-52 flex-col gap-6"
        data-testid="review-loading-skeleton"
      >
        <div className="space-y-4">
          <div className="text-xxs font-semibold uppercase tracking-wider text-muted-foreground/70">
            {t("deployments.agentTypeLabel")} {t("deployments.deployment")}
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-16 min-w-0 flex-1 rounded-lg" />
            <Skeleton className="h-5 w-5 rounded-full" />
            <Skeleton className="h-16 min-w-0 flex-1 rounded-lg" />
          </div>
        </div>

        <Skeleton className="h-12 rounded-lg" />

        <div className="space-y-3">
          <div className="space-y-2">
            <p className="text-base font-semibold">
              {t("deployments.selectVersionToReplace")}
            </p>
            <p className="text-sm text-muted-foreground">
              {t("deployments.selectedDeployedVersionWillUpdate", {
                next: "",
              })}
            </p>
          </div>

          <div className="space-y-2">
            {[1, 2, 3].map((row) => (
              <div
                key={row}
                className="rounded-lg border border-muted px-4 py-3"
              >
                <div className="flex min-h-10 items-center gap-4">
                  <Skeleton className="h-5 w-5 rounded-full" />
                  <div className="flex flex-1 items-center justify-between gap-3">
                    <div className="space-y-2">
                      <Skeleton className="h-5 w-56 max-w-full" />
                      <Skeleton className="h-4 w-44 max-w-full" />
                    </div>
                    <Skeleton className="h-5 w-10" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
