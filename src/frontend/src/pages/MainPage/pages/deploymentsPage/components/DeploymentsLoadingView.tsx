import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import Loading from "@/components/ui/loading";
import { Skeleton } from "@/components/ui/skeleton";

interface DeploymentsLoadingViewProps {
  activeSubTab: "deployments" | "providers";
}

export const DeploymentsLoadingView = ({
  activeSubTab,
}: DeploymentsLoadingViewProps) => {
  const skeletonIds = ["skeleton-1", "skeleton-2", "skeleton-3"];

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
        <Loading size={32} className="text-muted-foreground" />
        <p className="text-center text-sm font-medium text-muted-foreground pt-3">
          {activeSubTab === "deployments"
            ? "Loading your deployments..."
            : "Loading your providers..."}
        </p>
      </div>
    </div>
  );
};
