import React, { useState, useRef, useCallback } from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { Input } from "@/components/ui/input";
import SidebarDraggableComponent from "@/pages/FlowPage/components/flowSidebarComponent/components/sidebarDraggableComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";

const BasicExamplesSidebarSection: React.FC = () => {
  const examples = useFlowsManagerStore((state) => state.examples);
  const paste = useFlowStore((state) => state.paste);
  const [search, setSearch] = useState("");
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [order, setOrder] = useState<number[]>(examples ? examples.map((_, i) => i) : []);
  const searchInputRef = useRef<HTMLInputElement>(null);
  
  // Update order if examples change
  React.useEffect(() => {
    setOrder(examples ? examples.map((_, i) => i) : []);
  }, [examples]);

  const filteredExamples = examples
    ? order
        .map((i) => examples[i])
        .filter((example) =>
          example.name.toLowerCase().includes(search.toLowerCase())
        )
    : [];

  // Drag and drop handlers
  const handleDragStart = (idx: number) => setDraggedIdx(idx);
  const handleDragOver = (idx: number) => {
    if (draggedIdx === null || draggedIdx === idx) return;
    setOrder((prev) => {
      const newOrder = [...prev];
      const [removed] = newOrder.splice(draggedIdx, 1);
      newOrder.splice(idx, 0, removed);
      return newOrder;
    });
    setDraggedIdx(idx);
  };
  const handleDragEnd = () => setDraggedIdx(null);

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
      {/* Search Bar */}
      <div className="relative w-full flex-1 mb-2">
        <ForwardedIconComponent
          name="Search"
          className="absolute inset-y-0 left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-primary"
        />
        <Input
          ref={searchInputRef}
          type="search"
          className="w-full rounded-lg bg-background pl-8 text-sm"
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1 py-2">
        {filteredExamples.length > 0 ? (
          filteredExamples.map((example, idx) => (
            <div
              key={example.id}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragOver={(e) => {
                e.preventDefault();
                handleDragOver(idx);
              }}
              onDragEnd={handleDragEnd}
              className="bg-muted rounded-md"
              style={{ opacity: draggedIdx === idx ? 0.5 : 1 }}
            >
              <ShadTooltip content={example.name} side="right">
                <SidebarDraggableComponent
                  sectionName="basic_examples"
                  apiClass={{
                    display_name: example.name,
                    description: example.description,
                    icon: example.icon,
                    id: example.id,
                    template: {},
                    documentation: "",
                  }}
                  icon={example.icon ?? "Unknown"}
                  onDragStart={(event) => {
                    // Ensure example has display_name property to prevent errors
                    const exampleWithDisplayName = {
                      ...example,
                      display_name: example.name || example.id
                    };
                    // Format data properly for the drop handler
                    const data = JSON.stringify({
                      type: "genericNode",
                      node: {
                        ...exampleWithDisplayName,
                        template: example.template || {}
                      }
                    });
                    event.dataTransfer.setData("basicExample", data);
                    event.dataTransfer.setData("application/json", data);
                    event.dataTransfer.setData("text/plain", data);
                  }}
                  color="#e5e7eb"
                  itemName={example.id}
                  error={false}
                  display_name={example.name}
                  official={true}
                  beta={false}
                  legacy={false}
                  disabled={false}
                  // Add full flow on + button click
                  onClickPlus={() => handleAddFullFlow(example)}
                />
              </ShadTooltip>
            </div>
          ))
        ) : (
          <div className="text-muted-foreground text-xs px-2 py-4">No examples found.</div>
        )}
      </div>
    </div>
  );
};

export default BasicExamplesSidebarSection;