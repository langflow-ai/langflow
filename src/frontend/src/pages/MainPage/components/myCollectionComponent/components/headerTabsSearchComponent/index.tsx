import { useState } from "react";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {};

const HeaderTabsSearchComponent = ({}: HeaderTabsSearchComponentProps) => {
  const isFlowPage = window.location.pathname.includes("/flows");
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const [tabActive, setTabActive] = useState("Flows");

  return (
    <>
      <div className="flex items-end gap-4">
        <InputSearchComponent loading={isLoading} isFlowPage={isFlowPage} />

        <TabsSearchComponent
          tabsOptions={["Flows", "Components"]}
          setActiveTab={setTabActive}
          loading={isLoading}
          tabActive={tabActive}
        />
      </div>
    </>
  );
};
export default HeaderTabsSearchComponent;
