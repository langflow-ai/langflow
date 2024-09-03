import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useFolderStore } from "@/stores/foldersStore";
import { useIsFetching } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  type: string;
};

const MyCollectionComponent = ({ type }: MyCollectionComponentProps) => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const { data, isFetching } = useGetFolderQuery(
    {
      id: folderId ?? myCollectionId ?? "",
    },
    { enabled: !!folderId || !!myCollectionId },
  );

  const isLoadingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  return (
    <>
      <HeaderTabsSearchComponent loading={isFetching || isLoadingFolders} />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent
          key={type}
          type={type}
          currentFolder={data}
          isLoading={isFetching || isLoadingFolders}
        />
      </div>
    </>
  );
};
export default MyCollectionComponent;
