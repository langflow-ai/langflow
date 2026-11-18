import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

const PAGE_SIZE = 50;

function PayloadField({
  label,
  value,
  depth,
}: {
  label: string;
  value: unknown;
  depth: number;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(depth === 0);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const collection = value !== null && typeof value === "object";
  const array = Array.isArray(value);
  const keys = collection && !array ? Object.keys(value) : [];
  const count = array ? value.length : keys.length;
  const type =
    value === null
      ? "null"
      : array
        ? "array"
        : collection
          ? "object"
          : typeof value === "string" ||
              typeof value === "number" ||
              typeof value === "boolean"
            ? typeof value
            : "unknown";
  const name = <span className="font-medium">{label || '""'}</span>;
  const typeLabel = (
    <span className="rounded border px-1 font-sans text-[11px] text-muted-foreground">
      {t(`triggers.events.payloadTree.${type}`)}
    </span>
  );

  if (!collection || count === 0) {
    const text = collection
      ? array
        ? "[]"
        : "{}"
      : typeof value === "string"
        ? JSON.stringify(value)
        : String(value);
    return (
      <li className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-2 px-1 py-1">
          {name}
          {typeLabel}
          <code className="whitespace-pre-wrap break-all">{text}</code>
        </div>
      </li>
    );
  }

  const remaining = Math.max(0, count - visibleCount);
  return (
    <li className="min-w-0">
      <details
        open={expanded}
        onToggle={(event) => {
          if (event.target === event.currentTarget) {
            setExpanded(event.currentTarget.open);
          }
        }}
      >
        <summary className="cursor-pointer rounded px-1 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {name} {typeLabel}{" "}
          <span className="font-sans text-muted-foreground">
            {t(
              array
                ? "triggers.events.payloadTree.items"
                : "triggers.events.payloadTree.fields",
              { count },
            )}
          </span>
        </summary>
        {expanded && (
          <ul
            className={
              depth < 8
                ? "ml-2 border-l border-border pl-2"
                : "border-l border-border"
            }
          >
            {Array.from(
              { length: Math.min(visibleCount, count) },
              (_, index) => {
                const key = array ? String(index) : keys[index];
                return (
                  <PayloadField
                    key={key}
                    label={array ? `[${index}]` : key}
                    value={(value as Record<string, unknown>)[key]}
                    depth={depth + 1}
                  />
                );
              },
            )}
            {remaining > 0 && (
              <li>
                <Button
                  variant="ghost"
                  size="sm"
                  ignoreTitleCase
                  onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                >
                  {t("triggers.events.payloadTree.showMore", {
                    count: Math.min(PAGE_SIZE, remaining),
                  })}
                </Button>
              </li>
            )}
          </ul>
        )}
      </details>
    </li>
  );
}

/** Only renders the normalized, already redacted payload returned by the API. */
export default function TriggerPayloadTree({ payload }: { payload: unknown }) {
  const { t } = useTranslation();
  return (
    <div
      className="min-w-0 break-all rounded-md border bg-muted p-3 font-mono text-xs"
      data-testid="trigger-event-payload"
    >
      <ul>
        <PayloadField
          label={t("triggers.events.payload")}
          value={payload}
          depth={0}
        />
      </ul>
    </div>
  );
}
