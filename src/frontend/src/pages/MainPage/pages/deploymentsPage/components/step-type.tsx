import { ChevronDown } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useGetDeploymentLlms } from "@/controllers/API/queries/deployments/use-get-deployment-llms";
import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useErrorAlert } from "../hooks/use-error-alert";

const TYPE_OPTIONS = [
  {
    type: "agent" as const,
    label: "Agent",
    description: "Conversational agent with chat interface and tool calling",
    icon: "MessageSquare",
    iconBg: "border-accent-pink-foreground/20 bg-accent-pink-foreground/20",
  },
];

export default function StepType() {
  const {
    isEditMode,
    deploymentType,
    setDeploymentType,
    deploymentName,
    setDeploymentName,
    deploymentDescription,
    setDeploymentDescription,
    selectedLlm,
    setSelectedLlm,
    selectedInstance,
  } = useDeploymentStepper();

  const showErrorAlert = useErrorAlert();

  const providerId = selectedInstance?.id ?? "";
  const {
    data: llmData,
    isLoading: llmsLoading,
    error: llmsError,
  } = useGetDeploymentLlms({ providerId }, { enabled: !!providerId });
  const llmModels = llmData?.provider_data?.models ?? [];

  useEffect(() => {
    if (llmsError) {
      showErrorAlert("Failed to load models", llmsError);
    }
  }, [llmsError, showErrorAlert]);

  const [showScrollHint, setShowScrollHint] = useState(true);
  const contentRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return;
    // Find the actual scrollable viewport inside Radix SelectContent
    const viewport = node.querySelector("[data-radix-select-viewport]") ?? node;
    const checkScroll = () => {
      const isAtBottom =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 8;
      setShowScrollHint(!isAtBottom);
    };
    viewport.addEventListener("scroll", checkScroll);
    // Initial check after items render
    requestAnimationFrame(checkScroll);
  }, []);

  return (
    <div className="flex w-full flex-col gap-6 overflow-y-auto py-3">
      <h2 className="text-lg font-semibold">Deployment Type</h2>

      <div className="flex flex-col gap-3">
        <span className="text-sm font-medium">
          Choose Type <span className="text-destructive">*</span>
        </span>
        <div
          className="grid grid-cols-2 gap-3"
          role="radiogroup"
          aria-label="Deployment type"
        >
          {TYPE_OPTIONS.map((option) => (
            <label
              key={option.type}
              data-testid={`deployment-type-${option.type}`}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border bg-muted p-3 text-left transition-colors",
                deploymentType === option.type
                  ? "border-2 border-foreground"
                  : "border-border hover:border-muted-foreground",
              )}
            >
              <input
                type="radio"
                name="deployment-type"
                value={option.type}
                checked={deploymentType === option.type}
                onChange={() => setDeploymentType(option.type)}
                className="sr-only"
              />
              <div
                className={cn(
                  "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border p-2",
                  option.iconBg,
                )}
              >
                <ForwardedIconComponent
                  name={option.icon}
                  className="h-5 w-5"
                />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-medium">{option.label}</span>
                <p className="text-xs text-muted-foreground">
                  {option.description}
                </p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          Agent Name <span className="text-destructive">*</span>
        </span>
        <Input
          placeholder="e.g., Sales Bot"
          className="bg-muted"
          value={deploymentName}
          onChange={(e) => setDeploymentName(e.target.value)}
          disabled={isEditMode}
        />
        {isEditMode && (
          <span className="mt-1 text-xs text-muted-foreground">
            Name cannot be changed after creation.
          </span>
        )}
      </div>

      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          Model <span className="text-destructive">*</span>
        </span>
        <Select
          value={selectedLlm}
          onValueChange={setSelectedLlm}
          onOpenChange={(open) => open && setShowScrollHint(true)}
        >
          <SelectTrigger className="bg-muted focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-foreground">
            <SelectValue
              placeholder={llmsLoading ? "Loading models..." : "Select a model"}
            />
          </SelectTrigger>
          <SelectContent
            side="bottom"
            className="relative max-h-60 overflow-y-auto"
            ref={contentRef}
          >
            {!llmsLoading && llmModels.length === 0 && (
              <SelectItem value="__empty__" disabled>
                No models available for selected environment
              </SelectItem>
            )}
            {llmModels.map((model) => (
              <SelectItem key={model.model_name} value={model.model_name}>
                {model.model_name}
              </SelectItem>
            ))}
            {llmModels.length > 0 && (
              <div
                className={cn(
                  "pointer-events-none sticky -bottom-1 flex justify-center bg-gradient-to-t from-popover from-0% pb-1 pt-2 transition-opacity duration-200",
                  showScrollHint ? "opacity-100" : "opacity-0",
                )}
              >
                <ChevronDown className="h-4 w-4 animate-bounce text-muted-foreground" />
              </div>
            )}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">Description</span>
        <Textarea
          placeholder="Describe the agent's purpose..."
          rows={3}
          className="resize-none bg-muted placeholder:text-placeholder-foreground"
          value={deploymentDescription}
          onChange={(e) => setDeploymentDescription(e.target.value)}
        />
      </div>
    </div>
  );
}
