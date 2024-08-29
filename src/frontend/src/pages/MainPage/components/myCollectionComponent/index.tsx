import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useFolderStore } from "@/stores/foldersStore";
import { useParams } from "react-router-dom";
import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  type: string;
};

const MyCollectionComponent = ({ type }: MyCollectionComponentProps) => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const { data, isLoading } = useGetFolderQuery({
    id: folderId ?? myCollectionId ?? "",
  });
  const { isLoading: isLoadingFolders } = useGetFoldersQuery();

  return (
    <>
      <HeaderTabsSearchComponent loading={isLoading || isLoadingFolders} />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent
          key={type}
          type={type}
          currentFolder={data}
          isLoading={isLoading || isLoadingFolders}
        />
      </div>
    </>
  );
};
export default MyCollectionComponent;
