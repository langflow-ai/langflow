import { BASE_URL_API } from "../../../constants/constants";
import { api } from "../../../controllers/API/api";
import { FolderType } from "../entities";

export async function getFolders(): Promise<FolderType[]> {
  try {
    const response = await api.get(`${BASE_URL_API}folders/`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function addFolder(body: FolderType) {
  try {
    const response = await api.post(`${BASE_URL_API}folders/`, body);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function updateFolder(body: FolderType, folderId: string) {
  try {
    const response = await api.patch(
      `${BASE_URL_API}folders/${folderId}`,
      body
    );
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function deleteFolder(folderId: string) {
  try {
    const response = await api.delete(`${BASE_URL_API}folders/${folderId}`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function getFolderById(folderId: string) {
  try {
    const response = await api.get(`${BASE_URL_API}folders/${folderId}`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}

export async function getStarterProjects() {
  try {
    const response = await api.get(`${BASE_URL_API}folders/starter-projects`);
    return response?.data;
  } catch (error) {
    throw error;
  }
}
