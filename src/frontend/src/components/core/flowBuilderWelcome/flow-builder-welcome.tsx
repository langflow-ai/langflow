import { ArrowUp } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ModelSelector } from "@/components/core/assistantPanel/components/model-selector";
import { useAssistantSelectedModel } from "@/components/core/assistantPanel/hooks/use-assistant-selected-model";
import { useAutoGrowTextarea } from "@/components/core/assistantPanel/hooks/use-auto-grow-textarea";
import { useEnabledModels } from "@/components/core/assistantPanel/hooks/use-enabled-models";
import { Button } from "@/components/ui/button";
import type { SidebarSection } from "@/components/ui/sidebar";
import ModelProviderModal from "@/modals/modelProviderModal";
import { NAV_ITEMS } from "@/pages/FlowPage/components/flowSidebarComponent/components/sidebar-nav-items";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import {
  findStarterTemplate,
  type StarterTemplateNameKey,
} from "./helpers/find-starter-template";

const COMPOSER_MAX_HEIGHT_PX = 144; // 9rem — keeps the conversation above the composer readable

interface FlowBuilderWelcomeProps {
  /** Called with the trimmed text when the user submits the textarea. */
  onSubmit: (text: string) => void;
  /** Called with the stable ``name_key`` when a quick-template button is clicked. */
  onSelectTemplate: (nameKey: StarterTemplateNameKey) => void;
  /** Opens the existing full templates modal. */
  onBrowseMore: () => void;
  /** Called when the user dismisses the overlay (backdrop click, Escape). */
  onClose: () => void;
  /** Called when the user clicks an icon on the faux sidebar rail — the
   *  parent should open the real sidebar with that section pre-selected and
   *  then close the welcome. */
  onSelectRailItem: (section: SidebarSection) => void;
}

// Faux rail uses the SAME source of truth as the real ``SidebarSegmentedNav``
// — importing ``NAV_ITEMS`` directly so any future add/remove/reorder of
// sidebar sections is automatically reflected here. Keeps the two views from
// drifting apart.

const TEMPLATE_BUTTON_CLASS =
  "flex h-[3.125rem] w-[11rem] items-center justify-center gap-2.5 whitespace-nowrap rounded-xl border border-border bg-muted p-[0.8125rem] text-sm font-medium text-foreground transition-colors hover:bg-border";

export function FlowBuilderWelcome({
  onSubmit,
  onSelectTemplate,
  onBrowseMore,
  onClose,
  onSelectRailItem,
}: FlowBuilderWelcomeProps) {
  const [message, setMessage] = useState("");
  // Same server-owned cap the assistant panel uses (LANGFLOW_ASSISTANT_MAX_MESSAGE_LENGTH,
  // served by /config): this textarea posts to the same assistant endpoint.
  const maxMessageLength = useUtilityStore(
    (state) => state.assistantMaxMessageLength,
  );
  const limitHintId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useAutoGrowTextarea(textareaRef, message, COMPOSER_MAX_HEIGHT_PX);
  // AppInitPage holds every route back until the examples fetch settles, so an
  // empty list here means a policy blocked them, never "still loading".
  const examples = useFlowsManagerStore((state) => state.examples);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const hasSimpleAgent = findStarterTemplate(examples, "simple_agent") !== null;
  const hasVectorStoreRag =
    findStarterTemplate(examples, "vector_store_rag") !== null;
  // "Browse more…" opens the full modal, which is worth offering for any
  // surviving template, not just the two with their own button.
  const hasAnyTemplate = examples.length > 0;

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKey = (e: globalThis.KeyboardEvent) => {
      // Radix's DismissableLayer preventDefaults the Escape it consumes to
      // dismiss a dialog (e.g. the TemplatesModal opened from "Browse
      // more…") but does not stop propagation, so without this guard one
      // keypress would close both the modal and the welcome underneath,
      // stranding keyboard/screen-reader focus on the canvas (LE-2041 QA).
      if (e.key === "Escape" && !e.defaultPrevented) onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const messageLength = message.length;
  // The cap is hard, but never silent: the counter is always on screen and hitting the limit
  // names the environment variable that raises it.
  const isAtLimit = messageLength >= maxMessageLength;
  const { t } = useTranslation();
  // Shared model state with the AssistantPanel — picking a model here
  // persists to the same localStorage key, so the assistant opens with the
  // user's selection already applied (no second tour through the picker).
  const [selectedModel, setSelectedModel] = useAssistantSelectedModel();
  // No-provider hybrid: the AI textarea needs a model provider, but the
  // template buttons below don't. So when no provider is configured we swap
  // ONLY the input area for a configure-provider nudge and leave templates
  // fully usable.
  const { hasEnabledModels, isCatalogReady, isModelEnabled } =
    useEnabledModels();
  const [isProviderModalOpen, setIsProviderModalOpen] = useState(false);
  const selectedModelAuthorized = isModelEnabled(selectedModel);
  const canSend =
    message.trim().length > 0 && isCatalogReady && selectedModelAuthorized;
  const trySubmit = () => {
    const trimmed = message.trim();
    if (!canSend || trimmed.length > maxMessageLength) return;
    onSubmit(trimmed);
  };
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      trySubmit();
    }
  };
  // A settled empty catalog means configuration is needed. Pending, paused,
  // or failed policy resolution keeps the composer visible but inert so stale
  // cached data never masquerades as current authorization.
  const showNoProviderState = isCatalogReady && !hasEnabledModels;

  return (
    <div
      data-testid="flow-builder-welcome"
      className="pointer-events-auto absolute inset-0 z-30 flex items-center justify-center"
    >
      <button
        type="button"
        data-testid="flow-builder-welcome-backdrop"
        aria-label="Close welcome overlay"
        className="absolute inset-0 cursor-default bg-background/70"
        onClick={onClose}
      />

      {/* Faux collapsed sidebar rail — paints in front of the backdrop so the
          user sees the icon strip from the design mock. Visually mirrors the
          real ``SidebarSegmentedNav`` (same icons, same primitives, same
          40px-wide column with border-r). Any click on a rail icon dismisses
          the overlay — the real sidebar then takes over. */}
      {/* Floating wrapper rail — matches the design mock: a rounded pill
          inset from all canvas edges, nearly full-height, with the icons
          clustered at the top. Subtle border separates it from the canvas
          background. */}
      <aside
        data-testid="flow-builder-welcome-faux-rail"
        className="absolute left-1.5 top-1.5 z-10 flex w-10 animate-in flex-col items-center gap-1.5 rounded-lg border border-border bg-background p-1 duration-300 fade-in slide-in-from-left-2"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mirror the real always-visible nav, Agent tab included. */}
        {NAV_ITEMS.map((item) => {
          const tooltip = t(item.tooltip);
          return (
            <ShadTooltip key={item.id} content={tooltip} side="right">
              <button
                type="button"
                onClick={() => onSelectRailItem(item.id)}
                aria-label={tooltip}
                data-testid={`flow-builder-welcome-faux-rail-${item.id}`}
                className="flex h-8 w-8 items-center justify-center rounded-md p-0 text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                <ForwardedIconComponent
                  name={item.icon}
                  className="h-4.5 w-4.5"
                />
                <span className="sr-only">{tooltip}</span>
              </button>
            </ShadTooltip>
          );
        })}
      </aside>

      <div
        data-testid="flow-builder-welcome-panel"
        className="relative z-10 flex w-full max-w-[46rem] flex-col items-center gap-6 px-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h1 className="text-center text-4xl font-semibold text-foreground">
          {showNoProviderState
            ? t("flowBuilderWelcome.titleNoProvider")
            : t("flowBuilderWelcome.title")}
        </h1>

        {showNoProviderState ? (
          // No provider: drop the glow + gray input shell entirely. A clean,
          // minimal block — just the message + CTA — reads as a calm setup
          // step rather than a broken input. Templates below stay usable.
          <div
            data-testid="flow-builder-welcome-no-provider"
            className="flex w-full flex-col items-center gap-3 py-4 text-center"
          >
            <p className="max-w-[26rem] text-sm text-muted-foreground">
              {t("flowBuilderWelcome.noProviderDescription")}
            </p>
            <Button
              variant="outline"
              data-testid="flow-builder-welcome-configure-providers"
              className="gap-2"
              onClick={() => setIsProviderModalOpen(true)}
            >
              <ForwardedIconComponent name="Settings" className="h-4 w-4" />
              {t("flowBuilderWelcome.configureModelProviders")}
            </Button>
          </div>
        ) : (
          // Input container — design spec: 736×142px ≈ 46×8.875rem, 6px
          // radius. ``w-full`` + max-width for responsiveness; ``min-h`` so
          // it grows with the textarea. The relative shell hosts the
          // gradient glow behind the input; glow tokens mirror the
          // AssistantPanel.
          <div className="relative w-full">
            <div
              aria-hidden="true"
              className="welcome-glow-breath pointer-events-none absolute -bottom-2 left-1/2 h-16 w-3/4 rounded-full blur-2xl"
              style={{
                background:
                  "linear-gradient(90deg, hsl(var(--accent-assistant-purple) / 0.4) 0%, hsl(var(--accent-assistant-brand) / 0.5) 50%, hsl(var(--accent-assistant-purple) / 0.4) 100%)",
              }}
            />
            <div className="relative flex min-h-[8.875rem] w-full flex-col rounded-md border border-border bg-muted shadow-[0_0_15px_hsl(var(--accent-assistant-purple)/0.12),0_0_30px_hsl(var(--accent-assistant-brand)/0.08)]">
              <textarea
                ref={textareaRef}
                data-testid="flow-builder-welcome-textarea"
                placeholder={t("flowBuilderWelcome.textareaPlaceholder")}
                value={message}
                maxLength={maxMessageLength}
                aria-describedby={isAtLimit ? limitHintId : undefined}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={3}
                className="nopan nodelete nodrag noflow nowheel max-h-[9rem] flex-1 resize-none overflow-y-auto border-0 bg-transparent px-4 pt-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-0"
              />
              {isAtLimit && (
                <div
                  id={limitHintId}
                  role="status"
                  data-testid="flow-builder-welcome-limit-hint"
                  className="px-4 py-1 text-xs text-destructive"
                >
                  {t("assistant.messageLimitReached")}
                </div>
              )}
              <div className="flex items-center justify-between gap-2 px-2 pb-2">
                <ModelSelector
                  selectedModel={selectedModel}
                  onModelChange={setSelectedModel}
                />
                <div className="flex items-center gap-2">
                  <span
                    data-testid="flow-builder-welcome-char-count"
                    className={
                      isAtLimit
                        ? "text-xs tabular-nums text-destructive"
                        : "text-xs tabular-nums text-muted-foreground"
                    }
                  >
                    {messageLength}/{maxMessageLength}
                  </span>
                  <button
                    type="button"
                    data-testid="flow-builder-welcome-send-button"
                    aria-label={t("flowBuilderWelcome.sendLabel")}
                    title={t("flowBuilderWelcome.sendLabel")}
                    disabled={!canSend}
                    onClick={trySubmit}
                    className="flex h-8 w-8 items-center justify-center rounded-md bg-foreground text-background transition-colors hover:bg-foreground/90 disabled:opacity-50"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        {isProviderModalOpen && (
          <ModelProviderModal
            open={isProviderModalOpen}
            onClose={() => setIsProviderModalOpen(false)}
            modelType="llm"
            flowId={currentFlowId}
          />
        )}

        {/* Template buttons — design spec: 143×50px, 12px radius, 13px
            padding, 10px gap. A catalog policy can block any of these, and a
            button for a template that is gone would only fail on click, so
            each appears with its template. With nothing left to offer, the
            row becomes the one action still available: start blank. */}
        <div className="flex flex-col items-center gap-2">
          {hasAnyTemplate ? (
            <>
              <span className="text-sm text-muted-foreground">
                {t("flowBuilderWelcome.orTemplateLabel")}
              </span>
              <div className="flex flex-wrap items-center justify-center gap-3">
                {hasSimpleAgent && (
                  <button
                    type="button"
                    data-testid="flow-builder-welcome-template-simple-agent"
                    onClick={() => onSelectTemplate("simple_agent")}
                    className={TEMPLATE_BUTTON_CLASS}
                  >
                    <ForwardedIconComponent name="Bot" className="h-4 w-4" />
                    {t("flowBuilderWelcome.simpleAgentLabel")}
                  </button>
                )}
                {hasVectorStoreRag && (
                  <button
                    type="button"
                    data-testid="flow-builder-welcome-template-vector-store-rag"
                    onClick={() => onSelectTemplate("vector_store_rag")}
                    className={TEMPLATE_BUTTON_CLASS}
                  >
                    <ForwardedIconComponent
                      name="Database"
                      className="h-4 w-4"
                    />
                    {t("flowBuilderWelcome.vectorStoreRagLabel")}
                  </button>
                )}
                <button
                  type="button"
                  data-testid="flow-builder-welcome-browse-more"
                  onClick={onBrowseMore}
                  className={TEMPLATE_BUTTON_CLASS}
                >
                  <ForwardedIconComponent
                    name="LayoutGrid"
                    className="h-4 w-4"
                  />
                  {t("flowBuilderWelcome.browseMoreLabel")}
                </button>
              </div>
            </>
          ) : (
            <button
              type="button"
              data-testid="flow-builder-welcome-blank-flow"
              onClick={onClose}
              className={TEMPLATE_BUTTON_CLASS}
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              {t("flowBuilderWelcome.blankFlowLabel")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
