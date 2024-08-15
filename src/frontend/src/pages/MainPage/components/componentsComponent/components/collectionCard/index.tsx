import { useFolderStore } from "@/stores/foldersStore";
import React from "react";
import { Link, useNavigate } from "react-router-dom";
import CollectionCardComponent from "../../../../../../components/cardComponent";
import IconComponent from "../../../../../../components/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";
const CollectionCard = ({ item, type, isLoading, control }) => {
  const navigate = useNavigate();
  const isComponent = item.is_component ?? false;
  const editFlowLink = `/flow/${item.id}`;
  const editFlowButtonTestId = `edit-flow-button-${item.id}`;

  const folderUrl = useFolderStore((state) => state.folderUrl);
  const myCollectionIdFolder = useFolderStore((state) => state.myCollectionId);

  const hasFolderUrl = folderUrl != null && folderUrl !== "";
  const currentFolderUrl = hasFolderUrl ? folderUrl : myCollectionIdFolder;

  const handleClick = () => {
    if (!isComponent) {
      navigate(editFlowLink, { state: { folderId: currentFolderUrl } });
    }
  };

  return (
    <CollectionCardComponent
      data={{
        is_component: isComponent,
        ...item,
      }}
      disabled={isLoading}
      data-testid={editFlowButtonTestId}
      onClick={!isComponent ? handleClick : undefined}
      control={control}
    />
  );
};

export default CollectionCard;
