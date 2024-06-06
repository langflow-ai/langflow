import { useEffect } from "react";
import { getFolderById } from "../../../services";

// Custom Hook
function useFolderEffect(
  folderId,
  myCollectionId,
  location,
  setFolderUrl,
  setSelectedFlowsComponentsCards,
  handleSelectAll
) {
  useEffect(() => {
    setFolderUrl(folderId ?? "");
    setSelectedFlowsComponentsCards([]);
    handleSelectAll(false);
    getFolderById(folderId ? folderId : myCollectionId);
  }, [location]);
}

export default useFolderEffect;
