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

  const renderButton = () => {
    if (!isComponent) {
      return (
        <Link to={editFlowLink}>
          <Button
            tabIndex={-1}
            variant="outline"
            size="sm"
            className="whitespace-nowrap"
            data-testid={editFlowButtonTestId}
          >
            <IconComponent
              name="ExternalLink"
              className="main-page-nav-button select-none"
            />
            Edit Flow
          </Button>
        </Link>
      );
    }
    return null;
  };

  return (
    <CollectionCardComponent
      is_component={type === "component"}
      data={{
        is_component: isComponent,
        ...item,
      }}
      disabled={isLoading}
      data-testid={editFlowButtonTestId}
      button={renderButton()!}
      onClick={!isComponent ? handleClick : undefined}
      playground={!isComponent}
      control={control}
    />
  );
};

export default CollectionCard;
