import { SEARCH_TABS } from "@/constants/constants";
import { useCallback, useState } from "react";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {
  loading: boolean;
  onChangeTab: (tab: string) => void;
  onSearch: (search: string) => void;
  activeTab: string;
};

const HeaderTabsSearchComponent = ({
  loading,
  onChangeTab,
  onSearch,
  activeTab,
}: HeaderTabsSearchComponentProps) => {
  const [inputValue, setInputValue] = useState("");

  const handleChangeTab = useCallback(
    (tab: string) => {
      onChangeTab(tab);
    },
    [onChangeTab],
  );

  const handleSearch = useCallback(() => {
    onSearch(inputValue);
  }, [onSearch, inputValue]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setInputValue(e.target.value);
    },
    [],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        handleSearch();
      }
    },
    [handleSearch],
  );

  return (
    <>
      <div className="relative flex items-end gap-4">
        <InputSearchComponent
          loading={loading}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
        />
        <TabsSearchComponent
          tabsOptions={SEARCH_TABS}
          setActiveTab={handleChangeTab}
          loading={loading}
          tabActive={activeTab}
        />
      </div>
    </>
  );
};

export default HeaderTabsSearchComponent;
