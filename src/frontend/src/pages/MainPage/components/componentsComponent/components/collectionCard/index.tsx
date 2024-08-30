import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useParams } from "react-router-dom";
import CollectionCardComponent from "../../../../../../components/cardComponent";
const CollectionCard = ({ item, type, isLoading, control }) => {
  const navigate = useCustomNavigate();
  const isComponent = item.is_component ?? false;
  const editFlowButtonTestId = `edit-flow-button-${item.id}`;

  const { folderId } = useParams();

  const editFlowLink = `/flow/${item.id}${folderId ? `/folder/${folderId}` : ""}`;

  const handleClick = () => {
    if (!isComponent) {
      navigate(editFlowLink);
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
