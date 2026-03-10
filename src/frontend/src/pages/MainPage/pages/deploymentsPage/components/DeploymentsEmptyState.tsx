import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface DeploymentsEmptyStateProps {
  activeSubTab: "deployments" | "providers";
  onCreateDeployment: () => void;
  onAddProvider: () => void;
}

const skeletonIds = ["skeleton-1", "skeleton-2", "skeleton-3"];

export const DeploymentsEmptyState = ({
  activeSubTab,
  onCreateDeployment,
  onAddProvider,
}: DeploymentsEmptyStateProps) => {
  return (
    <div className="relative mt-4 h-full">
      {activeSubTab === "deployments" ? (
        <div className="pointer-events-none h-full opacity-30 [&_.ag-root-wrapper]:!bg-secondary [&_.ag-header]:!bg-secondary [&_.ag-body-viewport]:!bg-secondary [&_.ag-row]:!bg-secondary">
          <TableComponent
            columnDefs={[
              {
                headerName: "Name",
                field: "name",
                flex: 2,
                cellRenderer: () => <Skeleton className="h-4 w-28" />,
              },
              {
                headerName: "Status",
                field: "status",
                flex: 1,
                cellRenderer: () => <Skeleton className="h-4 w-16" />,
              },
              {
                headerName: "Health",
                field: "health",
                flex: 1,
                cellRenderer: () => <Skeleton className="h-4 w-16" />,
              },
              {
                headerName: "Attached",
                field: "attached",
                flex: 1,
                cellRenderer: () => <Skeleton className="h-4 w-10" />,
              },
              {
                headerName: "Provider",
                field: "provider",
                flex: 1,
                cellRenderer: () => <Skeleton className="h-4 w-20" />,
              },
              {
                headerName: "Last Modified",
                field: "lastModified",
                flex: 1.5,
                cellRenderer: () => <Skeleton className="h-4 w-24" />,
              },
              {
                headerName: "Test",
                field: "test",
                flex: 0.5,
                cellRenderer: () => <Skeleton className="h-4 w-10" />,
              },
              {
                headerName: "",
                field: "settings",
                width: 48,
                sortable: false,
                filter: false,
                resizable: false,
                cellRenderer: () => <Skeleton className="h-4 w-4" />,
              },
            ]}
            rowData={Array.from({ length: 3 }, (_, i) => ({
              id: `skeleton-${i}`,
            }))}
          />
        </div>
      ) : (
        <div className="pointer-events-none h-full opacity-30">
          <div className="grid grid-cols-3 gap-4">
            {skeletonIds.map((id) => (
              <div
                key={id}
                className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5"
              >
                <div className="flex items-start gap-3">
                  <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
                  <div className="flex w-full flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-4 w-32" />
                      <div className="flex items-center gap-1.5">
                        <Skeleton className="h-2 w-2 rounded-full" />
                        <Skeleton className="h-3 w-16" />
                      </div>
                    </div>
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-4 w-full" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col gap-1">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-4 w-24" />
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-4 w-8" />
                  </div>
                </div>
                <div className="flex gap-2 border-t border-border pt-3">
                  <Skeleton className="h-8 flex-1 rounded-md" />
                  <Skeleton className="h-8 flex-1 rounded-md" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute inset-0 z-50 flex flex-col items-center justify-center gap-3">
        {activeSubTab === "deployments" ? (
          <>
            <h3 className="text-lg font-semibold">No Deployments</h3>
            <p className="text-center text-sm text-muted-foreground pb-2">
              Create your first deployment to run your flows in <br />{" "}
              production.
            </p>
            <Button
              className="pointer-events-auto flex items-center gap-2"
              onClick={onCreateDeployment}
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              Create Deployment
            </Button>
          </>
        ) : (
          <>
            <h3 className="text-lg font-semibold">No Providers Connected</h3>
            <p className="text-center text-sm text-muted-foreground pb-2">
              Connect your first deployment provider to start <br /> deploying
              your flows to production environments.
            </p>
            <Button
              className="pointer-events-auto flex items-center gap-2"
              onClick={onAddProvider}
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              Add Provider
            </Button>
          </>
        )}
      </div>
    </div>
  );
};
