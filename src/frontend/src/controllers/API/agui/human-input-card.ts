/**
 * Human-in-the-loop card: build the interactive card from a pause payload, render
 * it into the chat (react-query cache for the new playground + useMessagesStore for
 * the legacy one), and persist the chosen action in the cache so the selection
 * survives the re-render the resume reattach triggers.
 */

import { updateMessage } from "@/components/core/playgroundComponent/chat-view/utils/message-utils";
import { queryClient } from "@/contexts";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type { ContentBlock, InteractiveContent } from "@/types/chat";
import type { Message } from "@/types/messages";
import type { WorkflowRunOptions } from "./run-agent";

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";

/** Centralizes the content-block structure: find a human_input content in a message. */
export function findHumanInputContent(
  contentBlocks: ContentBlock[] | undefined,
): InteractiveContent | undefined {
  return contentBlocks
    ?.flatMap((block) => block.contents ?? [])
    .find((content) => content?.type === "human_input") as
    | InteractiveContent
    | undefined;
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
 * Stamp the chosen action onto the card message in the react-query cache so the
 * selection is derived from a stable source — local React state is lost when the
 * resume reattach replays the stream and re-renders the message list.
 */
export function markHumanInputSubmitted(
  requestId: string,
  actionId: string,
): void {
  const messageId = `human-input-${requestId}`;
  forEachMessageCache((key, messages) => {
    if (!messages.some((m) => m.id === messageId)) return;
    queryClient.setQueryData(key, (old: Message[] = []) =>
      old.map((m) =>
        m.id === messageId
          ? {
              ...m,
              content_blocks: (m.content_blocks ?? []).map((block) => ({
                ...block,
                contents: (block.contents ?? []).map((c) =>
                  c?.type === "human_input"
                    ? { ...c, submitted_action: actionId }
                    : c,
                ),
              })),
            }
          : m,
      ),
    );
  });
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
    title: "Human input required",
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
  useFlowStore.getState().setAwaitingInput(true);
}
