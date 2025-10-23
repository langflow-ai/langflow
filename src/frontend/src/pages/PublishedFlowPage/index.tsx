import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import { useGetPublishedFlowForViewing } from "@/controllers/API/queries/published-flows/use-get-published-flow-for-viewing";
import { useTypesStore } from "@/stores/typesStore";
import ReadOnlyFlowViewer from "./components/ReadOnlyFlowViewer";

interface PublishedFlowPageProps {
  publishedFlowId: string;
}

export default function PublishedFlowPage({
  publishedFlowId,
}: PublishedFlowPageProps): JSX.Element {
  const types = useTypesStore((state) => state.types);

  // Ensure types are loaded for node rendering
  useGetTypes({
    enabled: Object.keys(types).length <= 0,
  });

  // Fetch published flow snapshot
  const { data: publishedFlow, isLoading: isLoadingPublishedFlow } =
    useGetPublishedFlowForViewing(publishedFlowId);

  if (isLoadingPublishedFlow) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">
            Loading published flow...
          </p>
        </div>
      </div>
    );
  }

  if (!publishedFlow) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <p className="text-sm text-muted-foreground">
          Published flow not found
        </p>
      </div>
    );
  }

  // Extract snapshot data - stays completely local to this component
  // Never touches FlowsManagerStore.currentFlow (no data loss)
  const nodes = publishedFlow.data?.nodes ?? [];
  const edges = publishedFlow.data?.edges ?? [];
  const viewport = publishedFlow.data?.viewport;

  console.log("[PublishedFlowPage] Extracted from publishedFlow:", nodes.length, "nodes");
  console.log("[PublishedFlowPage] Node IDs:", nodes.map(n => n.id));
  console.log("[PublishedFlowPage] publishedFlow object:", publishedFlow);

  return (
    <div className="flow-page-positioning h-full w-full">
      <ReadOnlyFlowViewer nodes={nodes} edges={edges} viewport={viewport} />
    </div>
  );
}
