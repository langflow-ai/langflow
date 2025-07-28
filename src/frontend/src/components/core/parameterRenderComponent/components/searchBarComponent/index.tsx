import { useState } from "react";
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
  placeholder = "Search tools...",
  onCategoryChange,
}: SearchBarComponentProps) => {
  const [selectedCategory, setSelectedCategory] = useState("All");

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
            <DropdownMenuItem
              key="All"
              onClick={() => handleCategoryChange("All")}
              className="cursor-pointer"
            >
              <span className="flex items-center gap-2 truncate px-2 py-1 text-sm">
                All
              </span>
            </DropdownMenuItem>
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
      <div className="relative flex w-full items-center">
        <Input
          placeholder={placeholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full border-none focus:ring-0"
          data-testid="search_bar_input"
        />
        <ForwardedIconComponent
          name="search"
          className="absolute right-3 h-4 w-4 text-muted-foreground"
        />
      </div>
    </div>
  );
};

export default SearchBarComponent;
