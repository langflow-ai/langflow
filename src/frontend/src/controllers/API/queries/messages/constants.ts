/**
 * Page size for message-history reads.
 *
 * `/monitor/messages` returns one bounded page anchored at the newest messages.
 * A caller that omits `limit` silently inherits the server default, so every
 * history read states the page size it renders instead — a flow with a long
 * history must never make the client download it in full.
 */
export const MESSAGE_HISTORY_PAGE_SIZE = 100;
