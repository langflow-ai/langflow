import React from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { Plus } from "lucide-react";
import { useSearchContext } from "@/pages/FlowPage/components/flowSidebarComponent";
// import { useSearchContext } from "../index";

const BasicExamplesSidebarSection: React.FC = () => {
  const examples = useFlowsManagerStore((state) => state.examples);
  const paste = useFlowStore((state) => state.paste);
  const { search } = useSearchContext();

  // Filter examples based on the global search from sidebar
  const filteredExamples = examples
    ? examples.filter((example) =>
        example.name.toLowerCase().includes((search ?? "").toLowerCase())
      )
    : [];

  // Handler to add full flow
  const handleAddFullFlow = (example) => {
    if (example && example.data && example.data.nodes && example.data.edges) {
      // Make sure template is properly included for all nodes
      const nodesWithTemplate = example.data.nodes.map(node => {
        // Ensure all nodes have proper template data
        if (node.data) {
          // For generic nodes with node data
          if (node.data.node) {
            return {
              ...node,
              data: {
                ...node.data,
                node: {
                  ...node.data.node,
                  // Use node's template if it exists, otherwise use example's template
                  template: node.data.node.template || example.template || {}
                }
              }
            };
          } 
          // For other node types that might not have the node property
          else {
            return {
              ...node,
              data: {
                ...node.data,
                template: node.data.template || example.template || {}
              }
            };
          }
        }
        return node;
      });
      
      // Center the pasted flow in the viewport
      paste({ 
        nodes: nodesWithTemplate, 
        edges: example.data.edges 
      }, { x: 0, y: 0, paneX: undefined, paneY: undefined });
    }
  };

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="flex flex-col gap-2 py-1">
        {filteredExamples.length > 0 ? (
          filteredExamples.map((example) => (
            <div
              key={example.id}
              className="relative group"
            >
              <div
                draggable
                onDragStart={e => {
                  const data = JSON.stringify(example);
                  e.dataTransfer.setData("basicExample", data);
                  e.dataTransfer.setData("text/plain", data);
                }}
                className="bg-muted hover:bg-muted/80 rounded-md p-2 cursor-grab active:cursor-grabbing transition-colors border border-border/50 hover:border-border flex items-center justify-between group"
                title={example.description}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {example.icon && (
                    <span className="text-sm flex-shrink-0">{example.icon}</span>
                  )}
                  <span 
                    className="text-sm font-medium text-foreground truncate"
                    title={example.name}
                  >
                    {example.name}
                  </span>
                </div>
                
                {/* Plus Icon - Only visible on hover */}
                <button
                  className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-1 hover:bg-background/80 rounded-sm flex-shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAddFullFlow(example);
                  }}
                  title="Add full flow"
                >
                  <Plus className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="text-muted-foreground text-xs px-2 py-4">
            {search ? "No examples match your search." : "No examples found."}
          </div>
        )}
      </div>
    </div>
  );
};

export default BasicExamplesSidebarSection;