import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { formatFileSize } from "@/utils/stringManipulation";
import { formatNumber } from "../utils/knowledgeBaseUtils";

interface KnowledgeBaseDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  knowledgeBase: KnowledgeBaseInfo | null;
}

// Mock data for source files and linked flows - can be replaced with real data later
const mockSourceFiles = [
  { id: "1", name: "document1.pdf", type: "PDF", icon: "File" },
  { id: "2", name: "data.csv", type: "CSV", icon: "File" },
  { id: "3", name: "manual.docx", type: "DOCX", icon: "File" },
];

const mockLinkedFlows = [
  { id: "1", name: "Customer Support Bot", icon: "Flow" },
  { id: "2", name: "Document Q&A System", icon: "Flow" },
];

const KnowledgeBaseDrawer = ({
  isOpen,
  onClose,
  knowledgeBase,
}: KnowledgeBaseDrawerProps) => {
  const [description, setDescription] = useState(
    "This knowledge base contains documents related to customer support and product documentation.",
  );

  if (!isOpen || !knowledgeBase) {
    return null;
  }

  return (
    <div className="flex h-full w-80 flex-col border-l bg-background">
      {/* Header */}
      <div className="flex items-center justify-between pt-4 px-4">
        <h3 className="font-semibold">{knowledgeBase.name}</h3>
        <Button variant="ghost" size="iconSm" onClick={onClose}>
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto pt-3">
        <div className="flex flex-col gap-4">
          {/* Description */}
          <div className="px-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                {description || "No description available."}
              </div>
            </div>
          </div>

          <Separator />

          {/* Embedding Provider */}
          <div className="space-y-2 px-4">
            <label className="text-sm font-medium">Embedding Provider</label>
            <div className="flex items-center gap-2">
              <div className="text-sm font-medium text-muted-foreground">
                {knowledgeBase.embedding_model || "Unknown"}
              </div>
            </div>
          </div>

          {/* Source Files */}
          <div className="space-y-3 px-4">
            <h4 className="text-sm font-medium ">Source Files</h4>
            <div className="space-y-2">
              {mockSourceFiles.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between py-1"
                >
                  <div className="flex items-center gap-2">
                    <ForwardedIconComponent
                      name={file.icon}
                      className="h-4 w-4 text-muted-foreground"
                    />
                    <div className="flex flex-col">
                      <div className="text-sm font-medium">{file.name}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="iconSm">
                      <ForwardedIconComponent
                        name="EllipsisVertical"
                        className="h-4 w-4"
                      />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Linked Flows */}
          <div className="space-y-3 px-4">
            <h4 className="text-sm font-medium ">Linked Flows</h4>
            <div className="space-y-2">
              {mockLinkedFlows.map((flow) => (
                <div
                  key={flow.id}
                  className="flex items-center justify-between py-2"
                >
                  <div className="flex items-center gap-2">
                    <ForwardedIconComponent
                      name="Workflow"
                      className="h-4 w-4 text-muted-foreground"
                    />
                    <div className="flex flex-col">
                      <div className="text-sm font-medium">{flow.name}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="iconSm">
                      <ForwardedIconComponent
                        name="EllipsisVertical"
                        className="h-4 w-4"
                      />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseDrawer;
