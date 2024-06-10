import { useState } from "react";
import { useLocation } from "react-router-dom";
import useAlertStore from "../../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../../../stores/foldersStore";
import { handleDownloadFolderFn } from "../../../../utils/handle-download-folder";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";

type HeaderTabsSearchComponentProps = {};

const HeaderTabsSearchComponent = ({}: HeaderTabsSearchComponentProps) => {
  const location = useLocation();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folderId = location?.state?.folderId || myCollectionId;
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const [tabActive, setTabActive] = useState("Flows");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);
  const [inputValue, setInputValue] = useState("");

  const setSearchFlowsComponents = useFlowsManagerStore(
    (state) => state.setSearchFlowsComponents,
  );

  const handleDownloadFolder = () => {
    if (allFlows.length === 0) {
      setErrorData({
        title: "Folder is empty",
        list: [],
      });
      return;
    }
    handleDownloadFolderFn(folderId);
  };

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
