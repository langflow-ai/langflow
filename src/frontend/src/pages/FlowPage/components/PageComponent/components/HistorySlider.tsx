import {
  type KeyboardEvent,
  type PointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import {
  describeOperation,
  fieldLabelsFrom,
} from "@/utils/flow-operations/describe";
import {
  entryContaining,
  graphAt,
  lastRevision,
  operationAt,
} from "@/utils/flow-operations/history";
import { cn } from "@/utils/utils";
import AuthorAvatar from "../../flowSidebarComponent/components/FlowVersionSidebar/components/AuthorAvatar";
import { formatTimestamp } from "../../flowSidebarComponent/components/FlowVersionSidebar/utils";

const PLAY_INTERVAL_MS = 700;
// Past this many entries, only those holding a saved version get a tick.
const MAX_TICKS = 200;

function ControlButton({
  icon,
  label,
  onClick,
  disabled,
  primary,
}: {
  icon: string;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40",
        primary &&
          "h-8 w-8 rounded-full bg-[#6366F1] text-white hover:bg-[#6366F1]/90 hover:text-white",
      )}
    >
      <ForwardedIconComponent name={icon} className="h-4 w-4" />
    </button>
  );
}

/**
 * Moves through the flow's whole retained history, one recorded change at a
 * time, across entries. Newest is at the top, like the timeline beside it.
 *
 * Every revision was replayed when the history loaded, so moving is a lookup.
 * The slider only changes the selection; the version sidebar draws it.
 */
export default function HistorySlider() {
  const { t } = useTranslation();
  const timeline = useRevisionPlaybackStore((s) => s.timeline);
  const revision = useRevisionPlaybackStore((s) => s.revision);
  const selectRevision = useRevisionPlaybackStore((s) => s.selectRevision);
  const [playing, setPlaying] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const min = timeline?.baseRevision ?? 0;
  const max = timeline ? lastRevision(timeline) : 0;
  const position = Math.min(Math.max(revision ?? max, min), max);
  const span = Math.max(max - min, 1);

  const ends = useMemo(() => {
    const inRange = (timeline?.entries ?? []).filter(
      (entry) => entry.end_revision > min && entry.end_revision <= max,
    );
    return inRange.length > MAX_TICKS
      ? inRange.filter((entry) => entry.versions.length > 0)
      : inRange;
  }, [timeline, min, max]);
  const entryEnds = useMemo(
    () =>
      (timeline?.entries ?? [])
        .map((entry) => entry.end_revision)
        .filter((end) => end >= min && end <= max),
    [timeline, min, max],
  );

  const go = (next: number) =>
    selectRevision?.(Math.min(Math.max(next, min), max));
  const previousEnd = [...entryEnds].reverse().find((end) => end < position);
  const nextEnd = entryEnds.find((end) => end > position);

  const positionRef = useRef(position);
  positionRef.current = position;
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      if (positionRef.current >= max) {
        setPlaying(false);
        return;
      }
      go(positionRef.current + 1);
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, max, selectRevision]);

  if (!timeline || max === min) return null;

  const offset = (r: number) => `${(1 - (r - min) / span) * 100}%`;
  const entry = entryContaining(timeline.entries, position);
  const operation = operationAt(timeline, position);
  const caption = operation
    ? describeOperation(operation, t, {
        fieldLabel: fieldLabelsFrom(graphAt(timeline, position)),
      }).join("; ")
    : t("flowHistory.playback.start");
  const author = operation?.actor ?? null;

  const revisionAt = (clientY: number) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect) return position;
    const fraction = 1 - (clientY - rect.top) / rect.height;
    return Math.round(min + Math.min(Math.max(fraction, 0), 1) * span);
  };
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    setPlaying(false);
    go(revisionAt(event.clientY));
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      go(revisionAt(event.clientY));
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number | undefined> = {
      ArrowUp: position + 1,
      ArrowRight: position + 1,
      ArrowDown: position - 1,
      ArrowLeft: position - 1,
      PageUp: nextEnd,
      PageDown: previousEnd,
      Home: min,
      End: max,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    event.stopPropagation();
    const next = moves[event.key];
    if (next !== undefined) {
      setPlaying(false);
      go(next);
    }
  };

  const entryStart = entry ? Math.max(entry.start_revision - 1, min) : null;

  return (
    <div className="pointer-events-auto absolute right-4 top-1/2 flex w-64 -translate-y-1/2 flex-col gap-3 rounded-xl border bg-background/95 p-3 shadow-lg backdrop-blur">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          <ForwardedIconComponent
            name="History"
            className="h-4 w-4 text-[#6366F1]"
          />
          {t("flowHistory.playback.title")}
        </span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {t("flowHistory.playback.step", {
            step: position - min,
            total: max - min,
          })}
        </span>
      </div>

      <div className="flex gap-3">
        <div
          ref={trackRef}
          role="slider"
          tabIndex={0}
          aria-label={t("flowHistory.playback.title")}
          aria-orientation="vertical"
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={position}
          aria-valuetext={caption}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onKeyDown={onKeyDown}
          className="relative h-56 w-6 shrink-0 cursor-pointer touch-none rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1]/50"
        >
          <span className="absolute inset-y-0 left-1/2 w-1 -translate-x-1/2 rounded-full bg-muted" />
          <span
            className="absolute bottom-0 left-1/2 w-1 -translate-x-1/2 rounded-full bg-[#6366F1]/30"
            style={{ top: offset(position) }}
          />
          {entryStart !== null && entry && (
            <span
              className="absolute left-1/2 w-1.5 -translate-x-1/2 rounded-full bg-[#6366F1]"
              style={{
                top: offset(entry.end_revision),
                bottom: `calc(100% - ${offset(entryStart)})`,
                minHeight: 4,
              }}
            />
          )}
          {ends.map((tick) => (
            <span
              key={tick.id}
              className={cn(
                "absolute left-1/2 h-px w-3 -translate-x-1/2",
                tick.versions.length > 0
                  ? "w-4 bg-[#6366F1]"
                  : "bg-muted-foreground/40",
              )}
              style={{ top: offset(tick.end_revision) }}
            />
          ))}
          <span
            className="absolute left-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#6366F1] bg-background shadow transition-[top] duration-100"
            style={{ top: offset(position) }}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col justify-between py-0.5 text-[11px] text-muted-foreground">
          <span>{t("flowHistory.playback.latest")}</span>
          <div className="flex flex-col gap-1.5 rounded-lg bg-muted/60 p-2">
            <div className="flex items-center gap-1.5">
              {author ? (
                <AuthorAvatar
                  id={author.id}
                  name={author.username}
                  className="h-5 w-5 text-[10px] ring-0"
                />
              ) : (
                <ForwardedIconComponent name="Flag" className="h-3.5 w-3.5" />
              )}
              <span className="truncate font-medium text-foreground">
                {author
                  ? (author.username ?? t("flowHistory.unknownAuthor"))
                  : t("flowHistory.playback.startShort")}
              </span>
            </div>
            <span className="line-clamp-4 break-words text-xs leading-snug text-foreground/80">
              {caption}
            </span>
            {entry?.created_at && (
              <span className="tabular-nums">
                {formatTimestamp(entry.created_at)}
              </span>
            )}
          </div>
          <span>{t("flowHistory.playback.earliest")}</span>
        </div>
      </div>

      <div className="flex items-center justify-between border-t pt-2">
        <ControlButton
          icon="SkipBack"
          label={t("flowHistory.playback.previousEntry")}
          onClick={() => previousEnd !== undefined && go(previousEnd)}
          disabled={previousEnd === undefined}
        />
        <ControlButton
          icon="StepBack"
          label={t("flowHistory.playback.back")}
          onClick={() => go(position - 1)}
          disabled={position <= min}
        />
        <ControlButton
          icon={playing ? "Pause" : "Play"}
          label={
            playing
              ? t("flowHistory.playback.pause")
              : t("flowHistory.playback.play")
          }
          onClick={() => {
            if (!playing && position >= max) go(min);
            setPlaying(!playing);
          }}
          primary
        />
        <ControlButton
          icon="StepForward"
          label={t("flowHistory.playback.forward")}
          onClick={() => go(position + 1)}
          disabled={position >= max}
        />
        <ControlButton
          icon="SkipForward"
          label={t("flowHistory.playback.nextEntry")}
          onClick={() => nextEnd !== undefined && go(nextEnd)}
          disabled={nextEnd === undefined}
        />
      </div>
    </div>
  );
}
