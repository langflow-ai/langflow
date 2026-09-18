import { useState } from "react";
import { useTranslation } from "react-i18next";
import PaginatorComponent from "@/components/common/paginatorComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useGetAuthorizationCapabilities,
  useGetSharedResources,
} from "@/controllers/API/queries/authorization";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export default function SharedWithMePage() {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const [flowPage, setFlowPage] = useState(1);
  const [flowSize, setFlowSize] = useState(20);
  const [projectPage, setProjectPage] = useState(1);
  const [projectSize, setProjectSize] = useState(20);
  const capabilities = useGetAuthorizationCapabilities();
  const ready = Boolean(
    capabilities.data?.enforcement_active && capabilities.data.service_ready,
  );
  const resources = useGetSharedResources(
    { flowPage, flowSize, projectPage, projectSize },
    { enabled: ready },
  );

  return (
    <main
      className="h-full w-full overflow-y-auto p-6"
      data-testid="shared-with-me-page"
    >
      <div className="mx-auto max-w-5xl space-y-5">
        <div>
          <h1 className="text-2xl font-semibold">{t("sharedWithMe.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("sharedWithMe.subtitle")}
          </p>
        </div>
        {capabilities.isLoading || resources.isLoading ? (
          <p role="status" className="text-sm text-muted-foreground">
            {t("sharedWithMe.loading")}
          </p>
        ) : capabilities.isError || !ready || resources.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{t("sharedWithMe.error")}</AlertDescription>
          </Alert>
        ) : (
          <Tabs defaultValue="flow">
            <TabsList aria-label={t("sharedWithMe.resourceFilter")}>
              <TabsTrigger value="flow">
                {t("sharedWithMe.resource.flow")}
              </TabsTrigger>
              <TabsTrigger value="project">
                {t("sharedWithMe.resource.project")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="flow">
              <ResourceList
                emptyText={t("sharedWithMe.empty.flow")}
                items={(resources.data?.flows.items ?? []).map((flow) => ({
                  id: flow.id,
                  name: flow.name,
                  owner: flow.owner_username,
                  onOpen: () => navigate(`/flow/${flow.id}`),
                }))}
              />
              <PaginatorComponent
                pageIndex={resources.data?.flows.page ?? flowPage}
                pageSize={resources.data?.flows.size ?? flowSize}
                pages={resources.data?.flows.pages ?? 1}
                totalRowsCount={resources.data?.flows.total ?? 0}
                paginate={(page, size) => {
                  setFlowPage(page);
                  setFlowSize(size);
                }}
              />
            </TabsContent>
            <TabsContent value="project">
              <ResourceList
                emptyText={t("sharedWithMe.empty.project")}
                items={(resources.data?.projects.items ?? []).map(
                  (project) => ({
                    id: project.id,
                    name: project.name,
                    owner: project.owner_username,
                    onOpen: () => navigate(`/all/folder/${project.id}`),
                  }),
                )}
              />
              <PaginatorComponent
                pageIndex={resources.data?.projects.page ?? projectPage}
                pageSize={resources.data?.projects.size ?? projectSize}
                pages={resources.data?.projects.pages ?? 1}
                totalRowsCount={resources.data?.projects.total ?? 0}
                paginate={(page, size) => {
                  setProjectPage(page);
                  setProjectSize(size);
                }}
              />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </main>
  );
}

function ResourceList({
  items,
  emptyText,
}: {
  items: Array<{
    id: string;
    name: string;
    owner?: string | null;
    onOpen: () => void;
  }>;
  emptyText: string;
}) {
  const { t } = useTranslation();
  if (!items.length)
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        {emptyText}
      </p>
    );
  return (
    <ul className="divide-y rounded-xl border">
      {items.map((item) => (
        <li key={item.id} className="flex flex-wrap items-center gap-3 p-4">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{item.name}</div>
            {item.owner && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("sharedWithMe.owner", { owner: item.owner })}
              </p>
            )}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={item.onOpen}
          >
            {t("sharedWithMe.open")}
          </Button>
        </li>
      ))}
    </ul>
  );
}
