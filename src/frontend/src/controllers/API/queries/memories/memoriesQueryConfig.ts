/** Maximum retry attempts for memory read queries. */
export const MEMORIES_RETRY_MAX_ATTEMPTS = 2;

const MEMORIES_RETRY_DELAY_MS = 1000;
const MEMORIES_RETRY_MAX_DELAY_MS = 10_000;

/** Exponential backoff capped at 10 s, shared by all memory query and mutation hooks. */
export const memoriesRetryDelay = (attemptIndex: number): number =>
  Math.min(
    MEMORIES_RETRY_DELAY_MS * 2 ** attemptIndex,
    MEMORIES_RETRY_MAX_DELAY_MS,
  );

/** Default page size for all memory infinite queries. */
export const MEMORIES_PAGE_SIZE = 50;
