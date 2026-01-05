import { memo } from "react";
import { Input } from "@/components/ui/input";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import ShortcutDisplay from "../../nodeToolbarComponent/shortcutDisplay";

export const SearchInput = memo(function SearchInput({
  searchInputRef,
  isInputFocused,
  search,
  handleInputFocus,
  handleInputBlur,
  handleInputChange,
}: {
  searchInputRef: React.RefObject<HTMLInputElement>;
  isInputFocused: boolean;
  search: string;
  handleInputFocus: (event: React.FocusEvent<HTMLInputElement>) => void;
  handleInputBlur: (event: React.FocusEvent<HTMLInputElement>) => void;
  handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className={`relative w-full flex-1 ${!ENABLE_NEW_SIDEBAR && "pb-2"}`}>
      <Input
        ref={searchInputRef}
        type="search"
        icon={"Search"}
        data-testid="sidebar-search-input"
        inputClassName="w-full rounded-lg bg-background text-sm"
        placeholder="Search"
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
        onChange={handleInputChange}
        value={search}
      />
      {!isInputFocused && search === "" && (
        <div
          className={`pointer-events-none absolute inset-y-0 right-2 top-[19px] flex -translate-y-1/2 items-center justify-between gap-2 text-sm text-muted-foreground ${ENABLE_NEW_SIDEBAR && "top-1/2"}`}
        >
          <span>
            <ShortcutDisplay sidebar shortcut="/" />
          </span>
        </div>
      )}
    </div>
  );
});

SearchInput.displayName = "SearchInput";
