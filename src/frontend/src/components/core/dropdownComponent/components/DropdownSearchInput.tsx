import type { ChangeEvent, KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { default as ForwardedIconComponent } from "../../../common/genericIconComponent";

export function DropdownSearchInput({
  onSearch,
  onKeyDown,
}: {
  onSearch: (event: ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center border-b px-2.5">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={onSearch}
        onKeyDown={onKeyDown}
        placeholder={t("input.searchOptions")}
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-[13px] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
        data-testid="dropdown_search_input"
      />
    </div>
  );
}
