const MAX_DIAGNOSTIC_ENTRIES = 20;
const MAX_RESPONSE_BODY_LENGTH = 1000;
const REQUEST_IDLE_SETTLE_MS = 25;
const SENSITIVE_KEY_PATTERN =
  /(?:api[_-]?key|token|secret|password|authorization|credential|session|cookie|database[_-]?url|dsn|private[_-]?key)/i;

function redactUriUserinfo(text) {
  return text.replace(/\b[a-z][a-z0-9+.-]*:\/\/[^\s"'<>]+/gi, (candidate) => {
    const authorityStart = candidate.indexOf("://") + 3;
    const suffix = candidate.slice(authorityStart);
    const authorityEndOffset = suffix.search(/[/?#]/);
    const authorityEnd =
      authorityEndOffset === -1
        ? candidate.length
        : authorityStart + authorityEndOffset;
    const authority = candidate.slice(authorityStart, authorityEnd);
    const userInfoEnd = authority.lastIndexOf("@");
    if (userInfoEnd === -1) {
      return candidate;
    }
    return `${candidate.slice(0, authorityStart)}[REDACTED]@${authority.slice(userInfoEnd + 1)}${candidate.slice(authorityEnd)}`;
  });
}

function redactTextualSecrets(text) {
  const assignmentsRedacted = text
    .replace(
      /((?:["']?[\w-]*(?:api[_-]?key|token|secret|password|authorization|credential|session|cookie|database[_-]?url|dsn|private[_-]?key)[\w-]*["']?\s*[:=]\s*))(["'])(?:\\.|(?!\2)[\s\S])*?\2/gi,
      "$1$2[REDACTED]$2",
    )
    .replace(
      /((?:["']?[\w-]*(?:api[_-]?key|token|secret|password|authorization|credential|session|cookie|database[_-]?url|dsn|private[_-]?key)[\w-]*["']?\s*[:=]\s*))(?!["']|\[REDACTED\]).*?(?=\s+["']?[\w-]+["']?\s*[:=]|["'](?:[,}\]]|$)|[,;&}\]\r\n]|$)/gi,
      "$1[REDACTED]",
    );
  return redactUriUserinfo(assignmentsRedacted).replace(
    /\b(bearer|basic)(\s+)[\w.+/=-]+/gi,
    "$1$2[REDACTED]",
  );
}

function redactStructuredValue(value) {
  if (Array.isArray(value)) {
    return value.map(redactStructuredValue);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [
        key,
        SENSITIVE_KEY_PATTERN.test(key)
          ? "[REDACTED]"
          : redactStructuredValue(nestedValue),
      ]),
    );
  }
  return typeof value === "string" ? redactTextualSecrets(value) : value;
}

export function sanitizeResponseExcerpt(
  body,
  maxLength = MAX_RESPONSE_BODY_LENGTH,
) {
  let sanitized;
  try {
    sanitized = JSON.stringify(redactStructuredValue(JSON.parse(body)));
  } catch {
    sanitized = body;
  }
  return redactTextualSecrets(sanitized).slice(0, maxLength);
}

export async function readResponseBodyWithTimeout(
  response,
  { timeoutMs, label },
) {
  const timeoutToken = Symbol("response-body-timeout");
  let timeoutId;

  try {
    const result = await Promise.race([
      Promise.resolve().then(() => response.text()),
      new Promise((resolve) => {
        timeoutId = setTimeout(() => resolve(timeoutToken), timeoutMs);
      }),
    ]);

    if (result === timeoutToken) {
      return {
        status: "timeout",
        diagnostic: sanitizeResponseExcerpt(
          `Timed out after ${timeoutMs}ms reading response body for ${label}.`,
        ),
      };
    }

    if (typeof result !== "string") {
      return {
        status: "error",
        diagnostic: sanitizeResponseExcerpt(
          `Could not read response body for ${label}.`,
        ),
      };
    }

    return { status: "success", body: result };
  } catch {
    return {
      status: "error",
      diagnostic: sanitizeResponseExcerpt(
        `Could not read response body for ${label}.`,
      ),
    };
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
  }
}

export function createPendingRequestTracker() {
  const pending = new Set();
  const idleWaiters = new Set();
  let idleTimeoutId;

  const notifyIfIdle = () => {
    if (pending.size !== 0 || idleTimeoutId !== undefined) {
      return;
    }
    // Wait one event-loop turn before declaring idle so an API request started
    // by a just-completed response joins the same bounded drain.
    idleTimeoutId = setTimeout(() => {
      idleTimeoutId = undefined;
      if (pending.size !== 0) {
        return;
      }
      for (const waiter of [...idleWaiters]) {
        waiter();
      }
    }, REQUEST_IDLE_SETTLE_MS);
  };

  return {
    start(request) {
      if (idleTimeoutId !== undefined) {
        clearTimeout(idleTimeoutId);
        idleTimeoutId = undefined;
      }
      pending.add(request);
    },
    finish(request) {
      pending.delete(request);
      notifyIfIdle();
    },
    async drain(timeoutMs) {
      await new Promise((resolve) => {
        let timeoutId;
        const settle = () => {
          clearTimeout(timeoutId);
          idleWaiters.delete(settle);
          resolve();
        };
        idleWaiters.add(settle);
        timeoutId = setTimeout(settle, timeoutMs);
        notifyIfIdle();
      });

      return [...pending];
    },
  };
}

export function createServerErrorContract() {
  return { expected: [], unexpected: [], droppedUnexpected: 0 };
}

export function expectServerError(contract, expectation) {
  if (
    !expectation.path.startsWith("/") ||
    expectation.path.includes("?") ||
    expectation.status < 500 ||
    expectation.status > 599 ||
    !Number.isInteger(expectation.count) ||
    expectation.count < 1
  ) {
    throw new Error(
      `Invalid server-error expectation: ${JSON.stringify(expectation)}`,
    );
  }
  contract.expected.push({
    ...expectation,
    method: expectation.method.toUpperCase(),
    observed: 0,
  });
}

export function observeServerError(contract, observed) {
  const expectation = contract.expected.find(
    (candidate) =>
      candidate.method === observed.method.toUpperCase() &&
      candidate.path === observed.path &&
      candidate.status === observed.status &&
      candidate.observed < candidate.count,
  );
  if (expectation) {
    expectation.observed += 1;
    return;
  }
  if (contract.unexpected.length < MAX_DIAGNOSTIC_ENTRIES) {
    contract.unexpected.push(observed);
  } else {
    contract.droppedUnexpected += 1;
  }
}

export function getServerErrorContractFailures(contract) {
  return {
    unexpected: contract.unexpected,
    droppedUnexpected: contract.droppedUnexpected,
    missing: contract.expected.filter(
      ({ count, observed }) => count !== observed,
    ),
  };
}
