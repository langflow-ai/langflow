import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InferTab } from "./components/InferTab";
import { MetricsTab } from "./components/MetricsTab";
import { ModelsTab } from "./components/ModelsTab";
import { OverviewTab } from "./components/OverviewTab";
import { RepositoryTab } from "./components/RepositoryTab";
import { useTritonConnection } from "./hooks/useTritonConnection";

export default function TritonServerDetailPage() {
  const { serverId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { server, isLoading } = useTritonConnection(serverId);
  const [tab, setTab] = useState("overview");

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (!server || !serverId) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-4">
        <p className="text-sm text-muted-foreground">
          {t("triton.servers.errorFetching")}
        </p>
        <Button
          variant="primary"
          onClick={() => navigate("/settings/triton-servers")}
        >
          {t("triton.detail.back")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit px-2 text-muted-foreground"
          onClick={() => navigate("/settings/triton-servers")}
        >
          <ForwardedIconComponent name="ChevronLeft" className="h-4 w-4" />
          {t("triton.detail.back")}
        </Button>
        <h2
          className="flex items-center gap-2 text-lg font-semibold tracking-tight"
          data-testid="triton-server-detail-title"
        >
          <ForwardedIconComponent
            name="Nvidia"
            className="h-5 w-5 text-primary"
          />
          {server.name}
        </h2>
        <span className="font-mono text-xs text-muted-foreground">
          {server.base_url}
        </span>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="flex-1">
        <TabsList>
          <TabsTrigger value="overview" data-testid="triton-tab-overview">
            {t("triton.detail.tabOverview")}
          </TabsTrigger>
          <TabsTrigger value="models" data-testid="triton-tab-models">
            {t("triton.detail.tabModels")}
          </TabsTrigger>
          <TabsTrigger value="repository" data-testid="triton-tab-repository">
            {t("triton.detail.tabRepository")}
          </TabsTrigger>
          <TabsTrigger value="inference" data-testid="triton-tab-inference">
            {t("triton.detail.tabInference")}
          </TabsTrigger>
          <TabsTrigger value="metrics" data-testid="triton-tab-metrics">
            {t("triton.detail.tabMetrics")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="mt-4">
          <OverviewTab serverId={serverId} />
        </TabsContent>
        <TabsContent value="models" className="mt-4">
          <ModelsTab serverId={serverId} />
        </TabsContent>
        <TabsContent value="repository" className="mt-4">
          <RepositoryTab serverId={serverId} />
        </TabsContent>
        <TabsContent value="inference" className="mt-4">
          <InferTab serverId={serverId} />
        </TabsContent>
        <TabsContent value="metrics" className="mt-4">
          <MetricsTab serverId={serverId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
