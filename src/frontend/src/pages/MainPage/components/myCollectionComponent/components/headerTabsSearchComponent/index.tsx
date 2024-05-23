import { useState } from "react";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import InputSearchComponent from "../inputSearchComponent";
import TabsSearchComponent from "../tabsComponent";
import { Button } from "../../../../../../components/ui/button";
import ForwardedIconComponent from "../../../../../../components/genericIconComponent";
import useAlertStore from "../../../../../../stores/alertStore";
import { handleDownloadFolderFn } from "../../../../utils/handle-download-folder";
import { useFolderStore } from "../../../../../../stores/foldersStore";
import { useLocation } from "react-router-dom";

type HeaderTabsSearchComponentProps = {};

const HeaderTabsSearchComponent = ({}: HeaderTabsSearchComponentProps) => {
  const location = useLocation();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folderId = location?.state?.folderId || myCollectionId;
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const [tabActive, setTabActive] = useState("Flows");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);

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
