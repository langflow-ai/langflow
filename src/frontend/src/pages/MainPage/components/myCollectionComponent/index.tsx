import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  type: string;
};

const MyCollectionComponent = ({ type }: MyCollectionComponentProps) => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const flows = useFlowsManagerStore((state) => state.flows);

  const { data: folderData, isFetching } = useGetFolderQuery(
    {
      id: folderId ?? myCollectionId ?? "",
    },
    { enabled: !!folderId || !!myCollectionId },
  );

  const data = {
    flows:
      folderData?.flows.filter((flow) =>
        flows?.find((f) => f.id === flow.id),
      ) ?? [],
    name: folderData?.name ?? "",
    description: folderData?.description ?? "",
    parent_id: folderData?.parent_id ?? "",
    components: folderData?.components ?? [],
  };

  const isLoadingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  const { deleteFlow, isDeleting } = useDeleteFlow();

  const isAddingFlow = !!useIsMutating({
    mutationKey: ["usePostAddFlow"],
    exact: true,
  });

  return (
    <>
      <HeaderTabsSearchComponent
        loading={isFetching || isLoadingFolders || isDeleting || isAddingFlow}
      />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent
          key={type}
          type={type}
          currentFolder={data}
          deleteFlow={deleteFlow}
          isLoading={
            isFetching || isLoadingFolders || isDeleting || isAddingFlow
          }
        />
      </div>
    </>
  );
};
export default MyCollectionComponent;
