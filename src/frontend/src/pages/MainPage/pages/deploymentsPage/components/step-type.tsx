import { keepPreviousData } from "@tanstack/react-query";
import { ChevronDown, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { useCheckAgentNames } from "@/controllers/API/queries/deployments";
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

function normalizeAgentName(name: string): string {
  return name.replace(/[\s-]/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
}

export default function StepType() {
  const {
    isEditMode,
    deploymentType,
    setDeploymentType,
    deploymentName,
    setDeploymentName,
    hasDeploymentNameFormatError,
    deploymentDescription,
    setDeploymentDescription,
    selectedLlm,
    setSelectedLlm,
    selectedInstance,
    hasAgentNameErrors,
    setHasAgentNameErrors,
    setIsAgentNameValidationPending,
  } = useDeploymentStepper();

  const showErrorAlert = useErrorAlert();

  const providerId = selectedInstance?.id ?? "";
  const {
    data: llmData,
    isLoading: llmsLoading,
    error: llmsError,
  } = useGetDeploymentLlms({ providerId }, { enabled: !!providerId });
  const PREFERRED_MODEL = "groq/openai/gpt-oss-120b";
  const llmModels = (() => {
    const raw = llmData?.provider_data?.models ?? [];
    const hasPreferred = raw.some((m) => m.model_name === PREFERRED_MODEL);
    const models = hasPreferred
      ? raw
      : [{ model_name: PREFERRED_MODEL }, ...raw];
    return models.sort((a, b) => {
      if (a.model_name === PREFERRED_MODEL) return -1;
      if (b.model_name === PREFERRED_MODEL) return 1;
      return 0;
    });
  })();

  useEffect(() => {
    if (llmsError) {
      showErrorAlert("Failed to load models", llmsError);
    }
  }, [llmsError, showErrorAlert]);

  const [debouncedDeploymentName, setDebouncedDeploymentName] =
    useState(deploymentName);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedDeploymentName(deploymentName);
    }, 500);
    return () => clearTimeout(timer);
  }, [deploymentName]);

  const isTypingName = deploymentName !== debouncedDeploymentName;
  const trimmedDeploymentName = debouncedDeploymentName.trim();
  const normalizedDeploymentName = useMemo(
    () => normalizeAgentName(trimmedDeploymentName).toLowerCase(),
    [trimmedDeploymentName],
  );
  const agentNamesToCheck = useMemo(() => {
    if (!trimmedDeploymentName) return [];
    return Array.from(
      new Set(
        [
          trimmedDeploymentName,
          normalizeAgentName(trimmedDeploymentName),
        ].filter(Boolean),
      ),
    );
  }, [trimmedDeploymentName]);

  const { data: checkAgentNameData, isFetching: isCheckingAgentName } =
    useCheckAgentNames(
      { providerId, names: agentNamesToCheck },
      {
        enabled: !!providerId && agentNamesToCheck.length > 0 && !isEditMode,
        placeholderData: keepPreviousData,
      },
    );

  const isAgentNameValidationPending =
    !isEditMode &&
    !!providerId &&
    deploymentName.trim().length > 0 &&
    (isTypingName || isCheckingAgentName);
  const shouldShowAgentNameAvailable =
    !isEditMode &&
    !!providerId &&
    !!trimmedDeploymentName &&
    !hasDeploymentNameFormatError &&
    !hasAgentNameErrors &&
    !isAgentNameValidationPending;

  useEffect(() => {
    setIsAgentNameValidationPending(isAgentNameValidationPending);
  }, [isAgentNameValidationPending, setIsAgentNameValidationPending]);

  useEffect(() => {
    if (isEditMode) {
      setHasAgentNameErrors(false);
      return;
    }
    if (!checkAgentNameData?.existing_names) {
      setHasAgentNameErrors(false);
      return;
    }

    // We normalize exactly as backend does for Watsonx: lowercase and strip some chars.
    // However, exact comparison is safer given backend returns the exact normalized names that matched.
    if (!trimmedDeploymentName) {
      setHasAgentNameErrors(false);
      return;
    }
    const exists = checkAgentNameData.existing_names.some((name) => {
      const normalizedExistingName = normalizeAgentName(name).toLowerCase();
      return (
        name.trim().toLowerCase() === trimmedDeploymentName.toLowerCase() ||
        normalizedExistingName === normalizedDeploymentName
      );
    });
    setHasAgentNameErrors(exists);
  }, [
    checkAgentNameData,
    isEditMode,
    normalizedDeploymentName,
    setHasAgentNameErrors,
    trimmedDeploymentName,
  ]);

  useEffect(() => {
    return () => setIsAgentNameValidationPending(false);
  }, [setIsAgentNameValidationPending]);

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
        <div className="relative">
          <Input
            placeholder="e.g., Sales Bot"
            className={cn(
              "bg-muted",
              hasDeploymentNameFormatError &&
                "border-destructive focus-visible:ring-0",
              hasAgentNameErrors &&
                "border-destructive/50 focus-visible:ring-destructive/30",
            )}
            value={deploymentName}
            onChange={(e) => setDeploymentName(e.target.value)}
            disabled={isEditMode}
            aria-invalid={hasDeploymentNameFormatError}
          />
          {isAgentNameValidationPending && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
        {hasDeploymentNameFormatError && (
          <span className="mt-1 text-xs text-destructive">
            Agent name must start with a letter.
          </span>
        )}
        {isEditMode ? (
          <span className="mt-1 text-xs text-muted-foreground">
            Name cannot be changed after creation.
          </span>
        ) : hasAgentNameErrors && !isAgentNameValidationPending ? (
          <span className="mt-1.5 flex items-center gap-1.5 text-xs text-destructive">
            <ForwardedIconComponent
              name="AlertTriangle"
              className="h-3.5 w-3.5"
            />
            Agent name already exists. Please choose a different name.
          </span>
        ) : shouldShowAgentNameAvailable ? (
          <span className="mt-1.5 flex items-center gap-1.5 text-xs text-success">
            <ForwardedIconComponent
              name="CheckCircle2"
              className="h-3.5 w-3.5"
            />
            Agent name is available.
          </span>
        ) : null}
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
