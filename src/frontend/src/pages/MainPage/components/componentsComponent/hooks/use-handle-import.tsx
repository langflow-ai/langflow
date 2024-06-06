import { UPLOAD_ERROR_ALERT } from "../../../../../constants/alerts_constants";

const useImportFlows = (
  uploadFlow,
  resetFilter,
  getFoldersApi,
  getFolderById,
  setSelectedFlowsComponentsCards,
  folderId,
  myCollectionId,
  setSuccessData,
  setErrorData
) => {
  const handleImport = () => {
    uploadFlow({ newProject: true, isComponent: false })
      .then(() => {
        resetFilter();
        getFoldersApi(true);
        if (!folderId || folderId === myCollectionId) {
          getFolderById(folderId ? folderId : myCollectionId);
        }
        setSelectedFlowsComponentsCards([]);
        setSuccessData({ title: "Flows imported successfully" });
      })
      .catch((error) => {
        setErrorData({
          title: UPLOAD_ERROR_ALERT,
          list: [error],
        });
      });
  };

  return { handleImport };
};

export default useImportFlows;
