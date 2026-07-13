/**
 * Human-in-the-loop card: build the interactive card from a pause payload, render
 * it into the chat (react-query cache for the new playground + useMessagesStore for
 * the legacy one), and persist the chosen action in the cache so the selection
 * survives the re-render the resume reattach triggers.
 */

import { updateMessage } from "@/components/core/playgroundComponent/chat-view/utils/message-utils";
import { queryClient } from "@/contexts";
import i18n from "@/i18n";
import useFlowStore from "@/stores/flowStore";
import { useHitlStore } from "@/stores/hitlStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type {
  ContentBlock,
  ContentBlockItem,
  InteractiveContent,
} from "@/types/chat";
import type { Message } from "@/types/messages";
import type { WorkflowRunOptions } from "./run-agent";

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";

/** Centralizes the content-block structure: find a human_input content in a message. */
export function findHumanInputContent(
  contentBlocks: ContentBlockItem[] | undefined,
): InteractiveContent | undefined {
  for (const item of contentBlocks ?? []) {
    if (item.type === "human_input") return item as InteractiveContent;
    // Shape-tolerant on purpose: cards persisted before the "group" discriminator
    // (and title-less groups) still carry the pause inside ``contents``.
    const contents = (item as ContentBlock).contents;
    if (Array.isArray(contents)) {
      const nested = contents.find(
        (content) => content?.type === "human_input",
      );
      if (nested) return nested as InteractiveContent;
    }
  }
  return undefined;
}

function toInteractiveContent(
  payload: Record<string, unknown>,
  jobId: string,
): InteractiveContent {
  return {
    type: "human_input",
    kind: (payload.kind as InteractiveContent["kind"]) ?? "node_input",
    request_id: String(payload.request_id ?? ""),
    prompt: payload.prompt as string | undefined,
    options: (payload.options as InteractiveContent["options"]) ?? [],
    schema: payload.schema as InteractiveContent["schema"],
    allowed_decisions: (payload.allowed_decisions as string[]) ?? [],
    job_id: jobId,
  };
}

/**
 * Reattach context per pause, keyed by request id. The interactive card resumes the
 * run itself (no prop-drilling through the chat render chain), so it needs the exact
 * run opts to stream the continued run back into the right session.
 */
const resumeRegistry = new Map<
  string,
  { jobId: string; opts: WorkflowRunOptions }
>();

export function getResumeContext(
  requestId: string,
): { jobId: string; opts: WorkflowRunOptions } | undefined {
  return resumeRegistry.get(requestId);
}

/**
 * Re-seed the resume context after a reload — the live run populates the registry,
 * but a page reload loses it, so reconnect rebuilds it from the persisted card. Only
 * fills a missing entry so it never clobbers a richer live one.
 */
export function registerResumeContext(
  requestId: string,
  jobId: string,
  opts: WorkflowRunOptions,
): void {
  if (!resumeRegistry.has(requestId))
    resumeRegistry.set(requestId, { jobId, opts });
}

function forEachMessageCache(
  fn: (key: unknown[], messages: Message[]) => void,
): void {
  for (const query of queryClient.getQueryCache().getAll()) {
    const key = query.queryKey;
    if (!Array.isArray(key) || key[0] !== MESSAGES_QUERY_KEY) continue;
    const messages = query.state.data as Message[] | undefined;
    if (Array.isArray(messages)) fn(key, messages);
  }
}

function cardAlreadyAnswered(messageId: string): boolean {
  let answered = false;
  forEachMessageCache((_key, messages) => {
    const msg = messages.find((m) => m.id === messageId);
    const content = findHumanInputContent(msg?.content_blocks);
    if (content?.submitted_action) answered = true;
  });
  return answered;
}

/**
 * Whether the pause in `payload` is one the user already answered (its card carries a
 * submitted_action). A resume reattach replays the run from the start and re-emits the
 * answered pause; the continuation may also carry a genuinely-new pause (a later
 * HumanInput), which is NOT answered and must still surface its card.
 */
export function isHumanInputCardAnswered(
  payload: Record<string, unknown>,
  jobId: string,
): boolean {
  const content = toInteractiveContent(payload, jobId);
  return cardAlreadyAnswered(`human-input-${content.request_id}`);
}

/**
 * Stamp the chosen action onto the card message in the react-query cache so the
 * selection is derived from a stable source — local React state is lost when the
 * resume reattach replays the stream and re-renders the message list.
 */
export function markHumanInputSubmitted(
  requestId: string,
  actionId: string,
): void {
  const messageId = `human-input-${requestId}`;
  const stampBlocks = (
    blocks: ContentBlockItem[] | undefined,
  ): ContentBlockItem[] =>
    (blocks ?? []).map((block) => {
      if (block.type === "human_input")
        return { ...block, submitted_action: actionId };
      const contents = (block as ContentBlock).contents;
      if (!Array.isArray(contents)) return block;
      return {
        ...block,
        contents: contents.map((c) =>
          c?.type === "human_input" ? { ...c, submitted_action: actionId } : c,
        ),
      };
    });
  forEachMessageCache((key, messages) => {
    if (!messages.some((m) => m.id === messageId)) return;
    queryClient.setQueryData(key, (old: Message[] = []) =>
      old.map((m) =>
        m.id === messageId
          ? { ...m, content_blocks: stampBlocks(m.content_blocks) }
          : m,
      ),
    );
  });
  // injectHumanInputCard writes both caches, so the resolve must stamp both — else a surface reading
  // useMessagesStore (legacy IOModal) keeps an interactive card after the other surface answered.
  const store = useMessagesStore.getState();
  const target = store.messages.find((m) => m.id === messageId);
  if (target) {
    store.updateMessage({
      ...target,
      content_blocks: stampBlocks(target.content_blocks),
    });
  }
}

/** Render the pause as an interactive card in the chat and flag awaiting-input. */
export function injectHumanInputCard(
  payload: Record<string, unknown>,
  jobId: string,
  opts: WorkflowRunOptions,
): void {
  const content = toInteractiveContent(payload, jobId);
  resumeRegistry.set(content.request_id, { jobId, opts });
  const messageId = `human-input-${content.request_id}`;
  // A resume reattach replays the pause event; if the user already answered (the
  // card carries submitted_action), re-injecting would clobber that choice. Skip.
  if (cardAlreadyAnswered(messageId)) {
    useFlowStore.getState().setAwaitingInput(true);
    return;
  }
  const block: ContentBlock = {
    type: "group",
    title: i18n.t("humanInput.required"),
    contents: [content],
    allow_markdown: true,
    component: "HumanInput",
  };
  const message: Message = {
    flow_id: opts.flowId,
    text: "",
    sender: "Machine",
    sender_name: "AI",
    session_id: opts.threadId ?? opts.flowId,
    timestamp: new Date().toISOString(),
    files: [],
    id: messageId,
    edit: false,
    background_color: "",
    text_color: "",
    content_blocks: [block],
  };
  // The new playground reads the react-query messages cache; the legacy IOModal
  // playground reads useMessagesStore. Write both so the card renders either way.
  updateMessage(message);
  useMessagesStore.getState().addMessage(message);
  // Canvas: surface the pause on the node that requested it (request_id = node_id:run_id).
  useHitlStore
    .getState()
    .setPending({ nodeId: content.request_id.split(":")[0], content });
  useFlowStore.getState().setAwaitingInput(true);
}
