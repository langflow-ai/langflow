import { useMemo, useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { cn, getNumberFromString } from "@/utils/utils";
import { swatchColors } from "@/utils/styleUtils";

// Use Case tabs from StudioHomePage
const USE_CASES: { title: string; id: string }[] = [
  { title: "Prior Authorization", id: "prior-auth" },
  { title: "Care Management", id: "classification" },
  { title: "Medical Record Review", id: "chart-review" },
  { title: "Document Analysis", id: "document-qa" },
  { title: "Claims Operations", id: "claims" },
];

// Template name mapping for Quick Start
const TEMPLATE_NAME_MAPPING = {
  "Basic Prompting Agent": "Create an Ask Auto Agent",
  "Clinical Extraction": "Create a Simple Extraction Agent",
  "Document Retrieval Agent": "Create a Document Retrieval Agent",
} as const;
const TEMPLATE_NAMES = Object.keys(
  TEMPLATE_NAME_MAPPING,
) as Array<keyof typeof TEMPLATE_NAME_MAPPING>;

// Template synonyms
const TEMPLATE_SYNONYMS: Record<string, string[]> = {
  "Basic Prompting Agent": [
    "Create an Chat Agent (Ask Auto)",
    "Basic Prompting",
  ],
  "Clinical Extraction": ["Create a Simple Extraction Agent"],
  "Document Retrieval Agent": [
    "Create a Document Retrieval Agent",
    "Document QA",
  ],
};

interface TemplatesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function TemplatesModal({
  isOpen,
  onClose,
}: TemplatesModalProps) {
  const navigate = useCustomNavigate();
  const [activeTab, setActiveTab] = useState<
    "quick-start" | "all" | "use-cases" | string
  >("quick-start");
  const [activeUseCaseTab, setActiveUseCaseTab] = useState(USE_CASES[0].title);

  // Get examples from store
  const examples = useFlowsManagerStore((state) => state.examples);

  // Quick Starts
  const quickStarts = useMemo(() => {
    const findExample = (primary: string, synonyms: string[]) => {
      const candidates = [primary, ...synonyms].map((n) => n.toLowerCase());
      return (
        examples.find((e) => candidates.includes((e.name || "").toLowerCase())) ||
        examples.find((e) =>
          candidates.some((n) => (e.name || "").toLowerCase().includes(n)),
        )
      );
    };

    return TEMPLATE_NAMES.map((templateKey) => {
      const display = TEMPLATE_NAME_MAPPING[templateKey];
      const ex = findExample(templateKey, TEMPLATE_SYNONYMS[templateKey] || []);
      if (!ex) return null;
      return {
        key: ex.id || display,
        title: display,
        description: ex.description ?? "",
        gradient: ex.gradient,
        icon: ex.icon,
        onClick: () => {
          navigate(`/create-agent?title=${encodeURIComponent(ex.name)}`);
          onClose();
        },
      };
    }).filter(Boolean) as Array<{
      key: string;
      title: string;
      description: string;
      gradient?: string;
      icon?: string;
      onClick: () => void;
    }>;
  }, [examples, navigate, onClose]);

  // Use Case Examples
  const activeUseCaseId = useMemo(
    () => USE_CASES.find((u) => u.title === activeUseCaseTab)?.id,
    [activeUseCaseTab],
  );
  const useCaseExamples = useMemo(
    () =>
      (examples || []).filter((ex) =>
        activeUseCaseId ? ex.tags?.includes(activeUseCaseId) : false,
      ),
    [examples, activeUseCaseId],
  );

  // All Templates
  const allTemplates = useMemo(() => examples || [], [examples]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background rounded-lg w-full max-w-6xl h-[80vh] flex overflow-hidden shadow-lg">
        {/* Left Sidebar */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-6 border-b">
            <h2 className="text-xl font-semibold">Templates</h2>
          </div>
          <nav className="flex-1 p-4 overflow-y-auto">
            <button
              onClick={() => setActiveTab("quick-start")}
              className={cn(
                "w-full text-left px-4 py-2 rounded-md mb-1 transition-colors",
                activeTab === "quick-start"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              )}
            >
              Quick Start
            </button>
            <button
              onClick={() => setActiveTab("all")}
              className={cn(
                "w-full text-left px-4 py-2 rounded-md mb-1 transition-colors",
                activeTab === "all"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              )}
            >
              All Templates
            </button>

            {/* Use Cases Section */}
            <div className="mt-2">
              <div className="px-4 py-2 text-sm font-semibold text-muted-foreground">
                Use Cases
              </div>
              {USE_CASES.map((useCase) => {
                const isActive = activeTab === useCase.id;
                return (
                  <button
                    key={useCase.id}
                    onClick={() => {
                      setActiveTab(useCase.id);
                      setActiveUseCaseTab(useCase.title);
                    }}
                    className={cn(
                      "w-full text-left px-4 py-2 rounded-md mb-1 transition-colors text-sm",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted text-muted-foreground"
                    )}
                  >
                    {useCase.title}
                  </button>
                );
              })}
            </div>
          </nav>
          <div className="p-4 border-t">
            <button
              onClick={() => {
                navigate("/genesis-flow");
                onClose();
              }}
              className="w-full flex items-center gap-2 px-4 py-3 border-2 border-dashed border-muted-foreground/30 rounded-lg hover:border-muted-foreground/50 hover:bg-muted/50 transition-colors"
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              <span className="text-sm font-medium">Blank Flow</span>
            </button>
          </div>
        </div>

        {/* Right Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="p-6 border-b flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {activeTab === "quick-start" && "Quick Start"}
              {activeTab === "all" && "All Templates"}
              {USE_CASES.find((u) => u.id === activeTab)?.title}
            </h3>
            <button
              onClick={onClose}
              className="p-2 hover:bg-muted rounded-md transition-colors"
              aria-label="Close"
            >
              <ForwardedIconComponent name="X" className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {/* Quick Start Tab */}
            {activeTab === "quick-start" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {quickStarts.map((qs) => {
                  const swatchIndex =
                    (qs.gradient && !isNaN(parseInt(qs.gradient))
                      ? parseInt(qs.gradient)
                      : getNumberFromString(qs.gradient ?? qs.key)) %
                    swatchColors.length;

                  return (
                    <Card
                      key={qs.key}
                      className="hover:shadow cursor-pointer transition-shadow"
                      onClick={qs.onClick}
                    >
                      <CardHeader>
                        <div className="flex items-start gap-3 mb-2">
                          <div
                            className={cn(
                              "flex h-10 w-10 items-center justify-center rounded-lg shrink-0",
                              swatchColors[swatchIndex]
                            )}
                          >
                            <ForwardedIconComponent
                              name={qs.icon || "Bot"}
                              className="h-5 w-5"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <CardTitle className="text-base">{qs.title}</CardTitle>
                          </div>
                        </div>
                        <CardDescription>{qs.description}</CardDescription>
                      </CardHeader>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* All Templates Tab */}
            {activeTab === "all" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {allTemplates.map((template) => {
                  const swatchIndex =
                    (template.gradient && !isNaN(parseInt(template.gradient))
                      ? parseInt(template.gradient)
                      : getNumberFromString(template.gradient ?? template.id)) %
                    swatchColors.length;

                  return (
                    <Card
                      key={template.id}
                      className="hover:shadow cursor-pointer transition-shadow"
                      onClick={() => {
                        navigate(`/create-agent?title=${encodeURIComponent(template.name)}`);
                        onClose();
                      }}
                    >
                      <CardHeader>
                        <div className="flex items-start gap-3 mb-2">
                          <div
                            className={cn(
                              "flex h-10 w-10 items-center justify-center rounded-lg shrink-0",
                              swatchColors[swatchIndex]
                            )}
                          >
                            <ForwardedIconComponent
                              name={template.icon || "Bot"}
                              className="h-5 w-5"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <CardTitle className="text-base">{template.name}</CardTitle>
                          </div>
                        </div>
                        <CardDescription>{template.description}</CardDescription>
                      </CardHeader>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* Use Cases Tab - Now handled by individual use case selections */}
            {USE_CASES.some((u) => u.id === activeTab) && (
              <>
                {useCaseExamples.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {useCaseExamples.map((ex) => {
                      const swatchIndex =
                        (ex.gradient && !isNaN(parseInt(ex.gradient))
                          ? parseInt(ex.gradient)
                          : getNumberFromString(ex.gradient ?? ex.id)) %
                        swatchColors.length;

                      return (
                        <Card
                          key={ex.id}
                          className="hover:shadow cursor-pointer transition-shadow"
                          onClick={() => {
                            navigate(`/create-agent?title=${encodeURIComponent(ex.name)}`);
                            onClose();
                          }}
                        >
                          <CardHeader>
                            <div className="flex items-start gap-3 mb-2">
                              <div
                                className={cn(
                                  "flex h-10 w-10 items-center justify-center rounded-lg shrink-0",
                                  swatchColors[swatchIndex]
                                )}
                              >
                                <ForwardedIconComponent
                                  name={ex.icon || "Bot"}
                                  className="h-5 w-5"
                                />
                              </div>
                              <div className="flex-1 min-w-0">
                                <CardTitle className="text-base">{ex.name}</CardTitle>
                              </div>
                            </div>
                            <CardDescription>{ex.description}</CardDescription>
                          </CardHeader>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    No templates found for {activeUseCaseTab}.
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
