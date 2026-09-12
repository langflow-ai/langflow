import type {
  AddFolderType,
  ProjectSaveResult,
} from "@/pages/MainPage/entities";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchPatchFolders {
  /**
   * PATCH applies per field, so a caller only sends what it means to change. A form that edits
   * the project's config has no business naming or renaming it.
   */
  data: Partial<AddFolderType>;
  folderId: string;
}

export const usePatchFolders: useMutationFunctionType<
  undefined,
  IPatchPatchFolders,
  ProjectSaveResult
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const patchFoldersFn = async (
    newFolder: IPatchPatchFolders,
  ): Promise<ProjectSaveResult> => {
    // A key left out of the payload leaves the stored value alone. An explicit null
    // project_config is a real value (it clears the config), which is why that one checks for
    // the key rather than for a truthy value.
    const payload = {
      ...(newFolder.data.name !== undefined
        ? { name: newFolder.data.name }
        : {}),
      ...(newFolder.data.description !== undefined
        ? { description: newFolder.data.description }
        : {}),
      ...(newFolder.data.flows !== undefined
        ? { flows_list: newFolder.data.flows }
        : {}),
      ...(newFolder.data.components !== undefined
        ? { components_list: newFolder.data.components }
        : {}),
      ...(newFolder.data.project_type
        ? { project_type: newFolder.data.project_type }
        : {}),
      ...(Object.hasOwn(newFolder.data, "project_config")
        ? { project_config: newFolder.data.project_config }
        : {}),
    };

    const res = await api.patch(
      `${getURL("PROJECTS")}/${newFolder.folderId}`,
      payload,
    );
    return res.data;
  };

  const mutation = mutate(["usePatchFolders"], patchFoldersFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders"] });
      // The open project is read through its own query, so a saved form has to invalidate it
      // too or the page keeps rendering the config it had before the save.
      queryClient.refetchQueries({ queryKey: ["useGetFolder"] });
    },
  });

  return mutation;
};
