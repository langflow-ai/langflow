import { type CSSProperties, type ReactNode, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import BaseModal from "@/modals/baseModal";
import { cn } from "@/utils/utils";
import type { InputProps } from "../../types";

// ---- Structured payload a component supplies to render read-only, dynamic data. ----
type Tone = "accent" | "muted" | "success" | "warning";
type Chip = { label: string; tone?: Tone; icon?: string };
type DataField = {
  name: string;
  type?: string;
  required?: boolean;
  description?: string;
};
type DataCard = { title: string; description?: string };
type Badge = string | { label: string; icon?: string; tone?: Tone };
type Section = {
  heading?: string;
  text?: string;
  rows?: { label?: string; value?: string }[];
  items?: string[];
  fields?: DataField[];
  tags?: string[];
  cards?: DataCard[];
  badges?: Badge[];
};
type DataDisplayPayload = {
  title?: string;
  subtitle?: string;
  version?: string;
  accent?: number; // hue override (0-360); otherwise derived from the title
  chips?: Chip[];
  sections?: Section[];
};

function parsePayload(value: unknown): DataDisplayPayload {
  if (!value) return {};
  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return {};
    }
  }
  if (typeof value === "object") return value as DataDisplayPayload;
  return {};
}

// Deterministic hue from a string so each subject gets its own, stable accent color.
function hueFromString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) % 360;
  return hash;
}

function monogramOf(title: string): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

// Toned pill styling. Accent uses the subject's derived hue; muted leans on theme tokens.
function toneStyle(
  tone: Tone | undefined,
  hue: number,
): CSSProperties | undefined {
  switch (tone) {
    case "accent":
      return {
        color: `hsl(${hue} 62% 55%)`,
        borderColor: `hsl(${hue} 55% 50% / 0.35)`,
        backgroundColor: `hsl(${hue} 55% 50% / 0.10)`,
      };
    case "success":
      return {
        color: "hsl(150 52% 45%)",
        borderColor: "hsl(150 45% 45% / 0.35)",
        backgroundColor: "hsl(150 45% 45% / 0.10)",
      };
    case "warning":
      return {
        color: "hsl(38 78% 50%)",
        borderColor: "hsl(38 75% 50% / 0.35)",
        backgroundColor: "hsl(38 75% 50% / 0.10)",
      };
    default:
      return undefined; // muted -> tokens via className
  }
}

const SectionLabel = ({ children }: { children: ReactNode }) =>
  children ? (
    <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
      {children}
    </div>
  ) : null;

function Pill({
  label,
  icon,
  tone,
  hue,
}: {
  label: string;
  icon?: string;
  tone?: Tone;
  hue: number;
}) {
  const style = toneStyle(tone, hue);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        !style && "border-border bg-muted/40 text-muted-foreground",
      )}
      style={style}
    >
      {icon && <ForwardedIconComponent name={icon} className="h-3.5 w-3.5" />}
      {label}
    </span>
  );
}

function SectionBody({ section, hue }: { section: Section; hue: number }) {
  const accentSolid = `hsl(${hue} 70% 55%)`;
  return (
    <div className="flex flex-col gap-3">
      {section.text && (
        <p className="text-sm leading-relaxed text-foreground/80">
          {section.text}
        </p>
      )}

      {section.rows && section.rows.length > 0 && (
        <div className="grid grid-cols-[minmax(5rem,auto)_1fr] gap-x-6 gap-y-1.5 text-sm">
          {section.rows.map((row, i) => (
            <div key={i} className="contents">
              <div className="text-muted-foreground">{row.label}</div>
              <div className="break-words text-foreground">{row.value}</div>
            </div>
          ))}
        </div>
      )}

      {section.fields && section.fields.length > 0 && (
        <div className="flex flex-col gap-2.5">
          {section.fields.map((field, i) => (
            <div key={i} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                  {field.name}
                </code>
                {field.type && (
                  <span className="text-xs text-muted-foreground">
                    {field.type}
                  </span>
                )}
                {field.required && (
                  <span
                    className="ml-auto inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide"
                    style={{ color: accentSolid }}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: accentSolid }}
                    />
                    required
                  </span>
                )}
              </div>
              {field.description && (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {field.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {section.cards && section.cards.length > 0 && (
        <div className="flex flex-col gap-2">
          {section.cards.map((card, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-muted/30 p-3 transition-colors hover:border-border/80 hover:bg-muted/50"
            >
              <div className="text-sm font-medium text-foreground">
                {card.title}
              </div>
              {card.description && (
                <div className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                  {card.description}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {section.tags && section.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {section.tags.map((tag, i) => (
            <Pill key={i} label={tag} tone="muted" hue={hue} />
          ))}
        </div>
      )}

      {section.items && section.items.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {section.items.map((item, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-sm text-foreground"
            >
              <span
                className="mt-[0.4rem] h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: accentSolid }}
              />
              <span className="break-words">{item}</span>
            </li>
          ))}
        </ul>
      )}

      {section.badges && section.badges.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {section.badges.map((badge, i) => {
            const label = typeof badge === "string" ? badge : badge.label;
            const icon = typeof badge === "string" ? undefined : badge.icon;
            const tone = typeof badge === "string" ? "muted" : badge.tone;
            return (
              <Pill key={i} label={label} icon={icon} tone={tone} hue={hue} />
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function DataDisplayComponent({
  value,
  id = "",
  editNode = false,
  disabled = false,
  showParameter = true,
  buttonText = "View",
  buttonIcon = "Eye",
}: InputProps<
  unknown,
  { buttonText?: string; buttonIcon?: string }
>): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const payload = useMemo(() => parsePayload(value), [value]);

  if (!showParameter) return null;

  const sections = payload.sections ?? [];
  const hasData = sections.length > 0 || !!payload.title;
  const isDisabled = disabled || !hasData;

  const title = payload.title ?? buttonText;
  const hue = payload.accent ?? hueFromString(title);
  const monogram = monogramOf(title);

  return (
    <div className="flex w-full" data-testid={id}>
      <BaseModal open={open} setOpen={setOpen} size="small-query">
        <BaseModal.Trigger asChild>
          <Button
            variant="primary"
            size="sm"
            disabled={isDisabled}
            className={cn(
              "w-full font-medium text-primary",
              editNode ? "h-fit px-3 py-0.5" : "",
            )}
            data-testid={
              editNode ? `data_display_edit_${id}` : `data_display_${id}`
            }
          >
            <ForwardedIconComponent name={buttonIcon} className="h-4 w-4" />
            {buttonText}
          </Button>
        </BaseModal.Trigger>

        <BaseModal.Header description={payload.subtitle ?? null}>
          <div className="flex min-w-0 items-center gap-3">
            <span
              aria-hidden
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white"
              style={{
                backgroundImage: `linear-gradient(135deg, hsl(${hue} 78% 62%), hsl(${(hue + 42) % 360} 74% 50%))`,
                boxShadow: `0 4px 12px -3px hsl(${hue} 70% 45% / 0.5)`,
              }}
            >
              {monogram}
            </span>
            <span className="truncate text-[17px] font-semibold text-foreground">
              {title}
            </span>
            {payload.version && (
              <span className="shrink-0 rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                v{payload.version}
              </span>
            )}
          </div>
        </BaseModal.Header>

        <BaseModal.Content>
          <div className="flex w-full flex-col gap-6 pt-1">
            {payload.chips && payload.chips.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {payload.chips.map((chip, i) => (
                  <Pill
                    key={i}
                    label={chip.label}
                    icon={chip.icon}
                    tone={chip.tone}
                    hue={hue}
                  />
                ))}
              </div>
            )}

            {sections.map((section, i) => (
              <div key={i} className="flex flex-col gap-2.5">
                <SectionLabel>{section.heading}</SectionLabel>
                <SectionBody section={section} hue={hue} />
              </div>
            ))}
          </div>
        </BaseModal.Content>
      </BaseModal>
    </div>
  );
}
