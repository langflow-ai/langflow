/* Hallmark · component: Hook editor · existing DESIGN.md tokens · P4 H4 E4 S5 R5 V4 */
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Icon from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateProjectFlow } from "@/controllers/API/queries/folders/use-create-instructions-flow";
import { useGetProjectFlowOutputsQuery } from "@/controllers/API/queries/folders/use-get-project-flow-outputs";
import type {
  FlowOutputChoice,
  HookBinding,
  HookEvent,
} from "@/pages/MainPage/entities";
import {
  bindingOf,
  moveHook,
  orderedHooks,
  outputKey,
  validHookTimeout,
} from "../flow-binding";
import { ProjectChoiceField } from "./project-choice-field";

export function HookFlowPicker({
  projectId,
  fieldName,
  agentId,
  value,
  disabled,
  onChange,
  onOpen,
}: {
  projectId: string;
  fieldName: string;
  agentId?: string;
  value: HookBinding[];
  disabled: boolean;
  onChange: (value: HookBinding[]) => void;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useGetProjectFlowOutputsQuery({
    projectId,
    fieldName,
  });
  const createFlow = useCreateProjectFlow();
  const [selectedKey, setSelectedKey] = useState("");
  const [creating, setCreating] = useState(false);
  const [creationError, setCreationError] = useState(false);
  const [createdId, setCreatedId] = useState<string>();
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const choices = (data ?? []).filter((choice) => choice.flow_id !== agentId);
  const selected = choices.find((choice) => outputKey(choice) === selectedKey);
  const locked = disabled || creating;
  const events: Record<HookEvent, string> = {
    before_llm_call: t("harness.hooksBeforeModel"),
    after_llm_call: t("harness.hooksAfterModel"),
    before_tool_call: t("harness.hooksBeforeTool"),
    after_tool_call: t("harness.hooksAfterTool"),
  };
  const add = (choice: FlowOutputChoice) => {
    onChange([
      ...value,
      {
        ...bindingOf(choice),
        on_event: "before_tool_call",
        mode: "observe",
        on_failure: "continue",
        timeout_seconds: 10,
        priority: Math.min(
          10000,
          Math.max(0, ...value.map((hook) => hook.priority ?? 0)) + 1,
        ),
      },
    ]);
    setSelectedKey("");
  };
  const update = (index: number, changes: Partial<HookBinding>) =>
    onChange(
      value.map((hook, i) => (i === index ? { ...hook, ...changes } : hook)),
    );
  const openLink = (flowId: string) =>
    `/flow/${flowId}?harnessField=${encodeURIComponent(fieldName)}`;

  return (
    <div className="min-w-0 space-y-4" data-testid="hook-flow-picker">
      <p className="text-sm text-muted-foreground">{t("harness.hooksHelp")}</p>
      {value.length > 0 && (
        <ol className="divide-y divide-border rounded-lg border border-border">
          {orderedHooks(value).map(({ hook, index }, position) => {
            const choice = choices.find(
              (item) => outputKey(item) === outputKey(hook),
            );
            const control = hook.mode === "control";
            const timeout = hook.timeout_seconds ?? 10;
            const stale = choice && choice.revision !== hook.revision;
            return (
              <li
                key={`${index}:${outputKey(hook)}`}
                className="min-w-0 space-y-3 p-4"
                data-testid={`hook-row-${position}`}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-1 text-sm tabular-nums text-muted-foreground">
                    {position + 1}.
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={openLink(hook.flow_id)}
                      onClick={onOpen}
                      className="block break-words text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {choice?.flow_name ??
                        t(
                          isLoading
                            ? "harness.loadingFlows"
                            : "harness.boundFlowUnavailable",
                        )}
                    </Link>
                    <p className="break-words text-xs text-muted-foreground">
                      {choice?.display_name ?? hook.output_name}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {([-1, 1] as const).map((direction) => (
                      <Button
                        key={direction}
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        aria-label={t(
                          direction === -1
                            ? "harness.moveHookUp"
                            : "harness.moveHookDown",
                          { count: position + 1 },
                        )}
                        disabled={
                          locked ||
                          position + direction < 0 ||
                          position + direction >= value.length
                        }
                        onClick={() =>
                          onChange(moveHook(value, position, direction))
                        }
                      >
                        <Icon
                          aria-hidden="true"
                          name={direction === -1 ? "ArrowUp" : "ArrowDown"}
                          className="h-4 w-4"
                        />
                      </Button>
                    ))}
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      disabled={locked}
                      aria-label={t("harness.removeHook", {
                        count: position + 1,
                      })}
                      onClick={() =>
                        onChange(value.filter((_, i) => i !== index))
                      }
                    >
                      <Icon aria-hidden="true" name="X" className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  <div className="min-w-0 space-y-1.5">
                    <span className="text-xs font-medium">
                      {t("harness.hookEvent")}
                    </span>
                    <ProjectChoiceField
                      className="h-9 w-full"
                      name={`hook-event-${position}`}
                      label={t("harness.hookEventLabel", {
                        count: position + 1,
                      })}
                      options={events}
                      value={hook.on_event}
                      disabled={locked}
                      onChange={(event) =>
                        update(index, {
                          on_event: event as HookEvent,
                          ...(event === "after_llm_call"
                            ? { mode: "observe" }
                            : {}),
                        })
                      }
                    />
                  </div>
                  <div className="min-w-0 space-y-1.5">
                    <span className="text-xs font-medium">
                      {t("harness.hookMode")}
                    </span>
                    <ProjectChoiceField
                      className="h-9 w-full"
                      name={`hook-mode-${position}`}
                      label={t("harness.hookModeLabel", {
                        count: position + 1,
                      })}
                      options={{
                        observe: t("harness.hookObserve"),
                        ...(hook.on_event === "after_llm_call"
                          ? {}
                          : { control: t("harness.hookControl") }),
                      }}
                      value={hook.mode ?? "observe"}
                      disabled={locked || hook.on_event === "after_llm_call"}
                      onChange={(mode) =>
                        update(index, {
                          mode: mode as HookBinding["mode"],
                          ...(mode === "control" ? { on_failure: "stop" } : {}),
                        })
                      }
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  {t(
                    hook.on_event === "after_llm_call"
                      ? "harness.hookAfterModelHelp"
                      : !control
                        ? "harness.hookObserveHelp"
                        : hook.on_event === "after_tool_call"
                          ? "harness.hookAfterToolHelp"
                          : hook.on_event === "before_llm_call"
                            ? "harness.hookBeforeModelHelp"
                            : "harness.hookBeforeToolHelp",
                  )}
                </p>
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  <div className="min-w-0 space-y-1.5">
                    <span className="text-xs font-medium">
                      {t("harness.hookFailure")}
                    </span>
                    <ProjectChoiceField
                      className="h-9 w-full"
                      name={`hook-failure-${position}`}
                      label={t("harness.hookFailureLabel", {
                        count: position + 1,
                      })}
                      options={{
                        continue: t("harness.hookContinue"),
                        stop: t("harness.hookStop"),
                      }}
                      value={hook.on_failure ?? "continue"}
                      disabled={locked || control}
                      onChange={(on_failure) =>
                        update(index, {
                          on_failure: on_failure as HookBinding["on_failure"],
                        })
                      }
                    />
                  </div>
                  <div className="min-w-0 space-y-1.5">
                    <label
                      htmlFor={`hook-timeout-${position}`}
                      className="text-xs font-medium"
                    >
                      {t("harness.hookTimeout")}
                    </label>
                    <Input
                      id={`hook-timeout-${position}`}
                      type="number"
                      className="h-9"
                      min={0}
                      max={300}
                      step="any"
                      disabled={locked}
                      value={Number.isFinite(timeout) ? timeout : ""}
                      aria-label={t("harness.hookTimeoutLabel", {
                        count: position + 1,
                      })}
                      aria-invalid={!validHookTimeout(timeout)}
                      aria-describedby={
                        !validHookTimeout(timeout)
                          ? `hook-timeout-error-${position}`
                          : undefined
                      }
                      onChange={(event) =>
                        update(index, {
                          timeout_seconds: event.target.valueAsNumber,
                        })
                      }
                    />
                    {!validHookTimeout(timeout) && (
                      <p
                        id={`hook-timeout-error-${position}`}
                        className="text-xs text-destructive"
                        role="alert"
                      >
                        {t("harness.hookTimeoutInvalid")}
                      </p>
                    )}
                  </div>
                </div>
                {control && (
                  <p className="text-xs text-muted-foreground">
                    {t("harness.hookControlFailureHelp")}
                  </p>
                )}
                {!isLoading && !isError && !choice && (
                  <p role="status" className="text-sm text-destructive">
                    {t("harness.hookUnavailableHelp")}
                  </p>
                )}
                {stale && (
                  <div
                    role="status"
                    className="flex flex-wrap items-center gap-2 text-sm"
                  >
                    <span>{t("harness.bindingChanged")}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={locked}
                      onClick={() =>
                        update(index, {
                          ...bindingOf(choice),
                          version_id: undefined,
                        })
                      }
                    >
                      {t("harness.updateBinding")}
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {isError && (
        <div role="alert" className="flex items-center gap-2 text-sm">
          <span>{t("harness.outputsLoadFailed")}</span>
          <Button
            size="sm"
            variant="outline"
            disabled={locked}
            onClick={() => void refetch()}
          >
            {t("harness.retryFlows")}
          </Button>
        </div>
      )}
      <div className="flex min-w-0 items-end gap-2">
        <div className="min-w-0 flex-1 space-y-1.5">
          <span className="text-xs font-medium">
            {t("harness.chooseHookFlow")}
          </span>
          <ProjectChoiceField
            className="h-9 w-full"
            name="hook-source"
            label={t("harness.chooseHookFlow")}
            options={Object.fromEntries(
              choices.map((choice) => [
                outputKey(choice),
                `${choice.flow_name} · ${choice.display_name}`,
              ]),
            )}
            value={selectedKey}
            placeholder={t("harness.chooseHookFlow")}
            disabled={
              locked || !agentId || isLoading || isError || !choices.length
            }
            onChange={setSelectedKey}
          />
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={locked || !agentId || !selected || isLoading || isError}
          onClick={() => selected && add(selected)}
        >
          {t("harness.addHook")}
        </Button>
      </div>
      {isLoading && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.loadingFlows")}
        </p>
      )}
      {!isLoading && !isError && !choices.length && (
        <p className="text-sm text-muted-foreground">
          {t("harness.noHookOutputs")}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={locked || !agentId}
          loading={creating}
          onClick={async () => {
            setCreating(true);
            setCreationError(false);
            try {
              const flow = await createFlow(projectId, fieldName);
              if (!mounted.current) return;
              setCreatedId(flow.id);
              // Creation succeeded even if refreshing the picker fails. Keep the open link.
              const refreshed = await refetch().catch(() => undefined);
              const outputs =
                refreshed?.data?.filter(
                  (choice) => choice.flow_id === flow.id,
                ) ?? [];
              if (mounted.current && outputs.length === 1) add(outputs[0]);
            } catch {
              if (mounted.current) setCreationError(true);
            } finally {
              if (mounted.current) setCreating(false);
            }
          }}
        >
          {t(creating ? "harness.creatingHookFlow" : "harness.createHookFlow")}
        </Button>
        {!agentId && (
          <span className="text-xs text-muted-foreground">
            {t("harness.hookChooseAgent")}
          </span>
        )}
      </div>
      {creationError && (
        <p role="alert" className="text-sm text-destructive">
          {t("harness.createHookFailed")}
        </p>
      )}
      {createdId && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("harness.hookFlowCreated")}{" "}
          <Link
            to={openLink(createdId)}
            onClick={onOpen}
            className="underline underline-offset-4"
          >
            {t("harness.openHookFlow")}
          </Link>
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {t("harness.hooksOrderHelp")}
      </p>
    </div>
  );
}
