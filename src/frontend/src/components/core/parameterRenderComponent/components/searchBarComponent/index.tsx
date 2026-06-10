import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";

interface SearchBarComponentProps {
  searchCategories?: string[];
  search: string;
  setSearch: (search: string) => void;
  placeholder?: string;
  onCategoryChange?: (category: string) => void;
}

const SearchBarComponent = ({
  searchCategories,
  search,
  setSearch,
  placeholder,
  onCategoryChange,
}: SearchBarComponentProps) => {
  const { t } = useTranslation();
  const [selectedCategory, setSelectedCategory] = useState(
    searchCategories?.[0] || "All",
  );

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    if (onCategoryChange) {
      onCategoryChange(category);
    }
  };

  return (
    <div className="flex w-full items-center rounded-md border">
      {searchCategories && searchCategories.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 pl-4 text-sm">
              <span className="truncate">{selectedCategory}</span>
              <ForwardedIconComponent
                name="chevron-down"
                className="flex h-4 w-4"
              />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {searchCategories.map((category) => (
              <DropdownMenuItem
                key={category}
                onClick={() => handleCategoryChange(category)}
                className="cursor-pointer"
              >
                <span className="flex items-center gap-2 truncate px-2 py-1 text-sm">
                  {category}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      <Input
        icon="search"
        placeholder={placeholder ?? t("toolsModal.searchPlaceholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        inputClassName="border-none focus:ring-0"
        data-testid="search_bar_input"
      />
    </div>
  );
};

export default SearchBarComponent;
