/* Hallmark · component-scope · existing design tokens · P4 H4 E4 S5 R5 V4 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateInstructionsFlow } from "@/controllers/API/queries/folders/use-create-instructions-flow";
import { useGetProjectFlowOutputsQuery } from "@/controllers/API/queries/folders/use-get-project-flow-outputs";
import type { FlowBinding, FlowOutputChoice } from "@/pages/MainPage/entities";

const outputKey = (value: FlowBinding) =>
  JSON.stringify([value.flow_id, value.node_id, value.output_name]);
const bindingOf = ({
  flow_id,
  node_id,
  output_name,
  revision,
}: FlowOutputChoice): FlowBinding => ({
  flow_id,
  node_id,
  output_name,
  revision,
});

export function InstructionsFlowPicker({
  projectId,
  fieldName,
  agentId,
  value,
  disabled,
  onChange,
  initialValue = "",
  onOpen,
}: {
  projectId: string;
  fieldName: string;
  agentId?: string;
  value?: FlowBinding;
  disabled: boolean;
  initialValue?: string;
  onOpen?: () => void;
  onChange: (value: FlowBinding | undefined) => void;
}) {
  const { t } = useTranslation();
  const createFlow = useCreateInstructionsFlow();
  const [creating, setCreating] = useState(false);
  const [creationError, setCreationError] = useState(false);
  const [createdId, setCreatedId] = useState<string>();
  const [choosing, setChoosing] = useState(false);
  const expanded = !!value || choosing;
  const { data, isLoading, isError, refetch } = useGetProjectFlowOutputsQuery(
    { projectId, fieldName },
    { enabled: expanded },
  );
  disabled = disabled || creating;
  const choices = (data ?? []).filter((choice) => choice.flow_id !== agentId);
  const selected =
    value && choices.find((choice) => outputKey(choice) === outputKey(value));
  if (!expanded)
    return (
      <Button
        className="self-start"
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
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-border p-3"
      data-testid="instructions-flow-picker"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">
          {t("harness.instructionsFromFlow")}
        </p>
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
            setCreating(true);
            setCreationError(false);
            try {
              const flow = await createFlow(projectId, fieldName, initialValue);
              setCreatedId(flow.id);
              // Creation already succeeded. A picker refresh failure must not invite duplicate retries.
              const refreshed = await refetch().catch(() => undefined);
              const output = refreshed?.data?.find(
                (choice) => choice.flow_id === flow.id,
              );
              if (output) onChange(bindingOf(output));
            } catch {
              setCreationError(true);
            } finally {
              setCreating(false);
            }
          }}
        >
          {t(
            creating
              ? "harness.creatingInstructionsFlow"
              : "harness.createInstructionsFlow",
          )}
        </Button>
        <span className="text-xs text-muted-foreground">
          {t("harness.instructionsBaselineHelp")}
        </span>
      </div>
      {creationError && (
        <p role="alert" className="text-sm text-destructive">
          {t("harness.createInstructionsFailed")}
        </p>
      )}
      {createdId && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.instructionsFlowCreated")}
          {value && value.flow_id !== createdId && (
            <Link
              className="ml-1 underline underline-offset-4"
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
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
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
              if (choice) onChange(bindingOf(choice));
            }}
          >
            <SelectTrigger
              className="h-auto min-h-8 w-full min-w-0 [&>span]:min-w-0 [&>span]:flex-1 [&>span]:text-left [&>svg]:shrink-0"
              aria-label={t("harness.chooseInstructionsFlow")}
            >
              <SelectValue
                placeholder={t(
                  isLoading
                    ? "harness.loadingFlows"
                    : "harness.chooseInstructionsFlow",
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
              {t("harness.noInstructionOutputs")}
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
                onClick={() => onChange(bindingOf(selected))}
              >
                {t("harness.updateBinding")}
              </Button>
            </div>
          )}
        </>
      )}
      {(value || createdId) && (
        <Link
          className="self-start text-sm underline underline-offset-4"
          to={`/flow/${value?.flow_id ?? createdId}?harnessField=${encodeURIComponent(fieldName)}`}
          onClick={onOpen}
        >
          {t("harness.openInstructionsFlow")}
        </Link>
      )}
      <p className="text-xs text-muted-foreground">
        {t("harness.bindingVersionHelp")}
      </p>
    </div>
  );
}
