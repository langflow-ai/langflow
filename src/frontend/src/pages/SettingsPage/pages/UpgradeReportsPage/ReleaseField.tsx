import { type KeyboardEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";

/** A version field that suggests releases and still accepts any typed version. */
export default function ReleaseField({
  id,
  value,
  onChange,
  releases,
  installed,
  disabled,
  invalid,
  describedBy,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  releases: string[];
  installed?: string;
  disabled: boolean;
  invalid: boolean;
  describedBy: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const all =
    installed && !releases.includes(installed)
      ? [...releases, installed]
      : releases;
  const options = all.filter((version) => version.includes(value.trim()));
  const shown = open && !disabled && options.length > 0;
  // The list can shrink under a highlight, so an index past its end means none.
  const active = shown && highlight < options.length ? highlight : -1;
  const listId = `${id}-options`;
  const close = () => {
    setOpen(false);
    setHighlight(-1);
  };
  const choose = (version: string) => {
    onChange(version);
    close();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (!options.length) return;
      const last = options.length - 1;
      setHighlight(
        event.key === "ArrowDown"
          ? active === last
            ? 0
            : active + 1
          : active <= 0
            ? last
            : active - 1,
      );
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      choose(options[active]);
    } else if (event.key === "Escape" && shown) {
      event.preventDefault();
      close();
    }
  };
  return (
    <div className="relative">
      <Input
        id={id}
        role="combobox"
        aria-expanded={shown}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        value={value}
        disabled={disabled}
        placeholder={t("settings.upgrade.check.targetPlaceholder")}
        spellCheck={false}
        endIcon="ChevronDown"
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onBlur={close}
        onKeyDown={onKeyDown}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
          setHighlight(-1);
        }}
      />
      {shown && (
        // tabIndex -1: Chrome makes a scrolling list a Tab stop, and tabbing to it would close it and drop focus.
        <ul
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-label={t("settings.upgrade.check.target")}
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 max-h-60 overflow-y-auto rounded-md border bg-popover py-1 text-sm text-popover-foreground shadow-lg"
          onMouseDown={(event) => event.preventDefault()}
        >
          {options.map((version, index) => (
            <li
              key={version}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className={`flex cursor-pointer items-center justify-between px-3 py-1.5 ${index === active ? "bg-muted" : "hover:bg-muted"}`}
              onClick={() => choose(version)}
            >
              <span>{t("settings.upgrade.check.release", { version })}</span>
              {version === installed && (
                <span className="text-xs text-muted-foreground">
                  {t("settings.upgrade.check.installed")}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
