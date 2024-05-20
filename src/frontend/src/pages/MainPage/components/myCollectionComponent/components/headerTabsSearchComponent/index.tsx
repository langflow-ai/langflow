import { useState } from "react";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {};

const HeaderTabsSearchComponent = ({}: HeaderTabsSearchComponentProps) => {
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const [tabActive, setTabActive] = useState("Flows");

  return (
    <>
      <div className="flex items-end gap-4">
        <InputSearchComponent loading={isLoading} />

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
