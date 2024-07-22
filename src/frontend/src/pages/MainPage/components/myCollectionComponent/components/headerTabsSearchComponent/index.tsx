import { useState } from "react";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {};

const HeaderTabsSearchComponent = ({}: HeaderTabsSearchComponentProps) => {
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const [tabActive, setTabActive] = useState("Flows");
  const [inputValue, setInputValue] = useState("");

  const setSearchFlowsComponents = useFlowsManagerStore(
    (state) => state.setSearchFlowsComponents,
  );

  return (
    <>
      <div className="relative flex items-end gap-4">
        <InputSearchComponent
          loading={isLoading}
          value={inputValue}
          onChange={(e) => {
            setSearchFlowsComponents(e.target.value);
            setInputValue(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setSearchFlowsComponents(inputValue);
            }
          }}
        />
        <TabsSearchComponent
          tabsOptions={["All", "Flows", "Components"]}
          setActiveTab={setTabActive}
          loading={isLoading}
          tabActive={tabActive}
        />
      </div>
    </>
  );
};
export default HeaderTabsSearchComponent;
