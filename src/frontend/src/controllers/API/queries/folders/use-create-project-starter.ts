import type { FolderType } from "@/pages/MainPage/entities";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useCreateProjectStarter: useMutationFunctionType<
  undefined,
  string,
  FolderType
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["createProjectStarter"],
    async (name: string) =>
      (
        await api.post(
          `${getURL("PROJECTS")}/starters/${encodeURIComponent(name)}`,
        )
      ).data,
    {
      ...options,
      // A lost response must not automatically create a second composition.
      retry: false,
      onSettled: async (data) => {
        await queryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
        const project = data as FolderType | undefined;
        if (!project?.id) return;
        // Routing checks this store before loading a project. The creation
        // response is authoritative even if the list refresh was stale/inactive.
        const { folders, setFolders } = useFolderStore.getState();
        if (!folders.some((folder) => folder.id === project.id)) {
          setFolders([
            ...folders,
            {
              ...project,
              parent_id: project.parent_id ?? "",
              flows: [],
              components: [],
              is_owner: true,
            },
          ]);
        }
      },
    },
  );
};
