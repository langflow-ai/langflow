import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import { FlowInsightsContent } from "@/modals/flowLogsModal/components/FlowInsightsContent";

export default function FlowInsightsPage(): JSX.Element {
  const { id } = useParams();
  const [searchParams] = useSearchParams();

  const defaultTab = useMemo(() => {
    const tab = searchParams.get("tab");
    return tab === "traces" ? "traces" : "logs";
  }, [searchParams]);

  const initialTraceId = searchParams.get("traceId");

  return (
    <PageLayout
      title="Flow Insights"
      description="Inspect component executions and traces."
      backTo={id ? `/flow/${id}/` : undefined}
    >
      <div className="flex w-full flex-1 flex-col overflow-hidden">
        <FlowInsightsContent
          flowId={id}
          defaultTab={defaultTab}
          initialTraceId={initialTraceId}
          refreshOnMount
        />
      </div>
    </PageLayout>
  );
}
