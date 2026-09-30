import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

// Search context for the sidebar
export type SearchContextType = {
  focusSearch: () => void;
  isSearchFocused: boolean;
  // Additional properties for the sidebar to use
  search?: string;
  setSearch?: (value: string) => void;
  searchInputRef?: React.RefObject<HTMLInputElement>;
  handleInputFocus?: () => void;
  handleInputBlur?: () => void;
  handleInputChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
};

export const SearchContext = createContext<SearchContextType | null>(null);

export function useSearchContext() {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error("useSearchContext must be used within SearchProvider");
  }
  return context;
}

// Create a provider that can be used at the FlowPage level
export function FlowSearchProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [search, setSearch] = useState("");
  const [isInputFocused, setIsInputFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null!);

  const focusSearchInput = useCallback(() => {
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, []);

  const handleInputFocus = useCallback(() => {
    setIsInputFocused(true);
  }, []);

  const handleInputBlur = useCallback(() => {
    setIsInputFocused(false);
  }, []);

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setSearch(event.target.value);
    },
    [],
  );

  const searchContextValue = useMemo(
    () => ({
      focusSearch: focusSearchInput,
      isSearchFocused: isInputFocused,
      // Also expose the search state and handlers for the sidebar to use
      search,
      setSearch,
      searchInputRef,
      handleInputFocus,
      handleInputBlur,
      handleInputChange,
    }),
    [
      focusSearchInput,
      isInputFocused,
      search,
      handleInputFocus,
      handleInputBlur,
      handleInputChange,
    ],
  );

  return (
    <SearchContext.Provider value={searchContextValue}>
      {children}
    </SearchContext.Provider>
  );
}
