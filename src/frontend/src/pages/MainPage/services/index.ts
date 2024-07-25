import { BASE_URL_API } from "../../../constants/constants";
import { api } from "../../../controllers/API/api";
import { FlowType } from "../../../types/flow";
import { AddFolderType, FolderType } from "../entities";

export async function getFolders(): Promise<FolderType[]> {
  try {
    const response = await api.get(`${BASE_URL_API}folders/`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function getFolderById(folderId: string): Promise<FolderType> {
  try {
    const response = await api.get(`${BASE_URL_API}folders/${folderId}`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function uploadFlowToFolder(
  flows: FormData,
  folderId: string,
): Promise<FlowType[]> {
  try {
    const url = `${BASE_URL_API}flows/upload/?folder_id=${encodeURIComponent(folderId)}`;

    const response = await api.post(url, flows);

    if (response?.status !== 201) {
      throw new Error(`HTTP error! status: ${response?.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}
