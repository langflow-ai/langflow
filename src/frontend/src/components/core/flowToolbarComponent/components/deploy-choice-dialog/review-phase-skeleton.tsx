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
      <DialogHeader>
        <DialogTitle>{t("deployments.reviewUpdate")}</DialogTitle>
        <DialogDescription>
          {t("deployments.reviewUpdateDescription")}
        </DialogDescription>
      </DialogHeader>

      <div
        className="flex min-h-52 flex-col gap-5"
        data-testid="review-loading-skeleton"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-muted-foreground">
            <span>{t("deployments.agentTypeLabel")}</span>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span>{t("deployments.deployment")}</span>
          </div>

          <div className="flex items-end justify-between gap-4">
            <Skeleton className="h-7 w-52" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-10 rounded-full" />
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-7 w-12 rounded-full" />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("deployments.chooseDeployedVersion")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("deployments.selectDeployedToolToReplace")}
            </p>
          </div>

          <div className="space-y-3">
            <div className="rounded-lg border border-border/60 bg-primary/5 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <Skeleton className="h-6 w-6 rounded-full" />
                <div className="flex flex-1 items-center justify-between gap-3">
                  <div className="min-w-0 space-y-2">
                    <Skeleton className="h-4 w-64 max-w-full" />
                    <p className="text-xs text-muted-foreground">
                      {t("deployments.willBeReplaced")}
                    </p>
                  </div>
                  <Skeleton className="h-7 w-12 rounded-full" />
                </div>
              </div>
            </div>

            {[1, 2].map((row) => (
              <div
                key={row}
                className="rounded-lg border border-border/50 px-4 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <Skeleton className="h-6 w-6 rounded-full" />
                  <div className="flex flex-1 items-center justify-between gap-3">
                    <Skeleton className="h-4 w-56 max-w-full" />
                    <Skeleton className="h-7 w-12 rounded-full" />
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
