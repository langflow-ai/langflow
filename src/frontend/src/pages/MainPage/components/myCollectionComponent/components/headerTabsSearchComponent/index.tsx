import { SEARCH_TABS } from "@/constants/constants";
import { useState } from "react";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {
  loading: boolean;
  onChangeTab: (tab: string) => void;
  onSearch: (search: string) => void;
};

const HeaderTabsSearchComponent = ({
  loading,
  onChangeTab,
  onSearch,
}: HeaderTabsSearchComponentProps) => {
  const [tabActive, setTabActive] = useState("All");
  const [inputValue, setInputValue] = useState("");

  const handleChangeTab = (tab: string) => {
    setTabActive(tab);
    onChangeTab(tab);
  };

  return (
    <>
      <div className="relative flex items-end gap-4">
        <InputSearchComponent
          loading={loading}
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onSearch(inputValue);
            }
          }}
        />
        <TabsSearchComponent
          tabsOptions={SEARCH_TABS}
          setActiveTab={handleChangeTab}
          loading={loading}
          tabActive={tabActive}
        />
      </div>
    </>
  );
};
export default HeaderTabsSearchComponent;
