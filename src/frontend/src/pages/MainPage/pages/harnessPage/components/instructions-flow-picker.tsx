/* Hallmark · component-scope · existing design tokens · P4 H4 E4 S5 R5 V4 */
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateInstructionsFlow } from "@/controllers/API/queries/folders/use-create-instructions-flow";
import { useGetProjectFlowOutputsQuery } from "@/controllers/API/queries/folders/use-get-project-flow-outputs";
import type {
  ContextBinding,
  FlowOutputChoice,
} from "@/pages/MainPage/entities";
import { bindingOf, outputKey, validFlowTimeout } from "../flow-binding";

export function HarnessFlowPicker({
  projectId,
  fieldName,
  agentId,
  value,
  disabled,
  onChange,
  initialValue = "",
  initialConfig,
  onOpen,
}: {
  projectId: string;
  fieldName: string;
  agentId?: string;
  value?: ContextBinding;
  disabled: boolean;
  initialValue?: string;
  initialConfig?: Record<string, unknown>;
  onOpen?: () => void;
  onChange: (value: ContextBinding | undefined) => void;
}) {
  const { t } = useTranslation();
  const isContext = fieldName === "context_strategy";
  const copy = isContext
    ? {
        title: "contextFromFlow",
        choose: "chooseContextFlow",
        create: "createContextFlow",
        creating: "creatingContextFlow",
        failed: "createContextFailed",
        baseline: "contextBaselineHelp",
        empty: "noContextOutputs",
        open: "openContextFlow",
        version: "contextBindingVersionHelp",
      }
    : {
        title: "instructionsFromFlow",
        choose: "chooseInstructionsFlow",
        create: "createInstructionsFlow",
        creating: "creatingInstructionsFlow",
        failed: "createInstructionsFailed",
        baseline: "instructionsBaselineHelp",
        empty: "noInstructionOutputs",
        open: "openInstructionsFlow",
        version: "bindingVersionHelp",
      };
  const createFlow = useCreateInstructionsFlow();
  const [creating, setCreating] = useState(false);
  const [creationError, setCreationError] = useState(false);
  const [createdId, setCreatedId] = useState<string>();
  const [choosing, setChoosing] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    setCreating(false);
    setCreationError(false);
    setCreatedId(undefined);
    return () => {
      generation.current += 1;
    };
  }, [projectId, fieldName, agentId]);
  const expanded = !!value || choosing;
  const { data, isLoading, isError, refetch } = useGetProjectFlowOutputsQuery(
    { projectId, fieldName },
    { enabled: expanded },
  );
  disabled = disabled || creating;
  const choices = (data ?? []).filter((choice) => choice.flow_id !== agentId);
  const selected =
    value && choices.find((choice) => outputKey(choice) === outputKey(value));
  const bind = (choice: FlowOutputChoice) =>
    onChange({
      ...bindingOf(choice),
      ...(isContext ? { timeout_seconds: value?.timeout_seconds ?? 30 } : {}),
    });
  if (!expanded)
    return (
      <Button
        className="h-auto self-start px-0 py-1 text-xs text-muted-foreground hover:text-foreground"
        variant="link"
        size="sm"
        disabled={disabled || !agentId}
        onClick={() => setChoosing(true)}
      >
        {t("harness.useFlowInstead")}
      </Button>
    );
  return (
    <div
      className="flex min-w-0 flex-col gap-4 rounded-xl bg-muted/40 p-4"
      data-testid={
        isContext ? "context-flow-picker" : "instructions-flow-picker"
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{t(`harness.${copy.title}`)}</p>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          onClick={() => {
            onChange(undefined);
            setChoosing(false);
          }}
        >
          {t("harness.useFormValue")}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || !agentId}
          onClick={async () => {
            const requestGeneration = generation.current;
            setCreating(true);
            setCreationError(false);
            try {
              const flow = initialConfig
                ? await createFlow(
                    projectId,
                    fieldName,
                    initialValue,
                    initialConfig,
                  )
                : await createFlow(projectId, fieldName, initialValue);
              if (requestGeneration !== generation.current) return;
              setCreatedId(flow.id);
              // Creation already succeeded. A picker refresh failure must not invite duplicate retries.
              const refreshed = await refetch().catch(() => undefined);
              if (requestGeneration !== generation.current) return;
              const outputs = refreshed?.data?.filter(
                (choice) => choice.flow_id === flow.id,
              );
              if (outputs?.length === 1) bind(outputs[0]);
            } catch {
              if (requestGeneration === generation.current)
                setCreationError(true);
            } finally {
              if (requestGeneration === generation.current) setCreating(false);
            }
          }}
        >
          {t(`harness.${creating ? copy.creating : copy.create}`)}
        </Button>
        <span className="text-xs text-muted-foreground">
          {t(`harness.${copy.baseline}`)}
        </span>
      </div>
      {creationError && (
        <p role="alert" className="text-sm text-destructive">
          {t(`harness.${copy.failed}`)}
        </p>
      )}
      {createdId && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.instructionsFlowCreated")}
          {value && value.flow_id !== createdId && (
            <Link
              className="ml-1 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              to={`/flow/${createdId}?harnessField=${encodeURIComponent(fieldName)}`}
              onClick={onOpen}
            >
              {t("harness.openCreatedInstructionsFlow")}
            </Link>
          )}
        </p>
      )}
      {isError ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span>{t("harness.outputsLoadFailed")}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => void refetch()}
          >
            {t("harness.retryFlows")}
          </Button>
        </div>
      ) : (
        <>
          <Select
            value={value ? outputKey(value) : ""}
            disabled={disabled || isLoading || !choices.length}
            onValueChange={(key) => {
              const choice = choices.find(
                (choice) => outputKey(choice) === key,
              );
              if (choice) bind(choice);
            }}
          >
            <SelectTrigger
              className="h-auto min-h-8 w-full min-w-0 [&>span]:min-w-0 [&>span]:flex-1 [&>span]:text-left [&>svg]:shrink-0"
              aria-label={t(`harness.${copy.choose}`)}
            >
              <SelectValue
                placeholder={t(
                  isLoading ? "harness.loadingFlows" : `harness.${copy.choose}`,
                )}
              />
            </SelectTrigger>
            <SelectContent className="max-w-[calc(100vw-2rem)]">
              {value && !selected && (
                <SelectItem value={outputKey(value)} disabled>
                  {t("harness.boundFlowUnavailable")}
                </SelectItem>
              )}
              {choices.map((choice) => (
                <SelectItem key={outputKey(choice)} value={outputKey(choice)}>
                  <span className="block min-w-0">
                    <span className="block truncate">{choice.flow_name}</span>
                    <span className="block whitespace-normal break-words text-xs text-muted-foreground">
                      {choice.display_name}
                    </span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!isLoading && !choices.length && (
            <p className="text-sm text-muted-foreground">
              {t(`harness.${copy.empty}`)}
            </p>
          )}
          {!isLoading && value && !selected && (
            <p role="status" className="text-sm text-muted-foreground">
              {t("harness.bindingUnavailableHelp")}
            </p>
          )}
          {value && selected && value.revision !== selected.revision && (
            <div
              className="flex flex-wrap items-center gap-2 text-sm"
              role="status"
            >
              <span>{t("harness.bindingChanged")}</span>
              <Button
                size="sm"
                variant="outline"
                disabled={disabled}
                onClick={() => bind(selected)}
              >
                {t("harness.updateBinding")}
              </Button>
            </div>
          )}
        </>
      )}
      {isContext && value && (
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor={`context-timeout-${projectId}`}
            className="text-xs font-medium"
          >
            {t("harness.contextTimeout")}
          </label>
          <Input
            id={`context-timeout-${projectId}`}
            type="number"
            min={0}
            max={300}
            step="any"
            className="h-9 w-28"
            value={
              Number.isFinite(value.timeout_seconds ?? 30)
                ? (value.timeout_seconds ?? 30)
                : ""
            }
            disabled={disabled}
            aria-invalid={!validFlowTimeout(value.timeout_seconds ?? 30)}
            aria-describedby={`context-timeout-help-${projectId}`}
            onChange={(event) =>
              onChange({
                ...value,
                timeout_seconds: event.currentTarget.valueAsNumber,
              })
            }
          />
          <p
            id={`context-timeout-help-${projectId}`}
            className="text-xs text-muted-foreground"
          >
            {t("harness.contextTimeoutHelp")}
          </p>
          {!validFlowTimeout(value.timeout_seconds ?? 30) && (
            <p role="alert" className="text-sm text-destructive">
              {t("harness.contextTimeoutInvalid")}
            </p>
          )}
        </div>
      )}
      {(value || createdId) && (
        <Link
          className="self-start text-sm underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          to={`/flow/${value?.flow_id ?? createdId}?harnessField=${encodeURIComponent(fieldName)}`}
          onClick={onOpen}
        >
          {t(`harness.${copy.open}`)}
        </Link>
      )}
      <p className="text-xs text-muted-foreground">
        {t(`harness.${copy.version}`)}
      </p>
    </div>
  );
}

export const InstructionsFlowPicker = HarnessFlowPicker;
