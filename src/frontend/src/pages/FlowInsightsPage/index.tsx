import { useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { FlowInsightsContent } from "@/modals/flowLogsModal/components/FlowInsightsContent";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

export default function FlowInsightsPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useCustomNavigate();
  const flows = useFlowsManagerStore((state) => state.flows);

  const initialTraceId = searchParams.get("traceId");

  useEffect(() => {
    if (!id || flows === undefined) return;
    const flowExists = flows.some((flow) => flow.id === id);
    if (!flowExists) {
      navigate("/all");
    }
  }, [id, flows, navigate]);

  return (
    <PageLayout
      title="Flow Insights"
      description="Inspect component executions and traces."
      backTo={id ? `/flow/${id}/` : undefined}
    >
      <div
        className="flex w-full flex-1 flex-col overflow-hidden"
        data-testid="flow-insights-page"
      >
        <FlowInsightsContent
          flowId={id}
          initialTraceId={initialTraceId}
          refreshOnMount
        />
      </div>
    </PageLayout>
  );
}
