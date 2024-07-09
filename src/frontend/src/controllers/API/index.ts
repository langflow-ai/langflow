import { ColDef, ColGroupDef } from "ag-grid-community";
import { AxiosRequestConfig, AxiosResponse } from "axios";
import { Edge, Node, ReactFlowJsonObject } from "reactflow";
import { BASE_URL_API, MAX_BATCH_SIZE } from "../../constants/constants";
import { api } from "../../controllers/API/api";
import {
  APIObjectType,
  APITemplateType,
  Component,
  CustomComponentRequest,
  LoginType,
  ProfilePicturesTypeAPI,
  Users,
  VertexBuildTypeAPI,
  VerticesOrderTypeAPI,
  changeUser,
  resetPasswordType,
  sendAllProps,
} from "../../types/api/index";
import { UserInputType } from "../../types/components";
import { FlowStyleType, FlowType } from "../../types/flow";
import { Message } from "../../types/messages";
import { StoreComponentResponse } from "../../types/store";
import { FlowPoolType } from "../../types/zustand/flow";
import { extractColumnsFromRows } from "../../utils/utils";
import {
  APIClassType,
  BuildStatusTypeAPI,
  InitTypeAPI,
  PromptTypeAPI,
  UploadFileTypeAPI,
  errorsTypeAPI,
} from "./../../types/api/index";

/**
 * Fetches all objects from the API endpoint.
 *
 * @param {boolean} force_refresh - Whether to force a refresh of the data.
 * @returns {Promise<AxiosResponse<APIObjectType>>} A promise that resolves to an AxiosResponse containing all the objects.
 */
export async function getAll(
  force_refresh: boolean = true,
): Promise<AxiosResponse<APIObjectType>> {
  return await api.get(`${BASE_URL_API}all?force_refresh=${force_refresh}`);
}

const GITHUB_API_URL = "https://api.github.com";

export async function getRepoStars(owner: string, repo: string) {
  try {
    const response = await api.get(`${GITHUB_API_URL}/repos/${owner}/${repo}`);
    return response.data.stargazers_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

/**
 * Sends data to the API for prediction.
 *
 * @param {sendAllProps} data - The data to be sent to the API.
 * @returns {AxiosResponse<any>} The API response.
 */
export async function sendAll(data: sendAllProps) {
  return await api.post(`${BASE_URL_API}predict`, data);
}

export async function postValidateCode(
  code: string,
): Promise<AxiosResponse<errorsTypeAPI>> {
  return await api.post(`${BASE_URL_API}validate/code`, { code });
}

/**
 * Checks the prompt for the code block by sending it to an API endpoint.
 * @param {string} name - The name of the field to check.
 * @param {string} template - The template string of the prompt to check.
 * @param {APIClassType} frontend_node - The frontend node to check.
 * @returns {Promise<AxiosResponse<PromptTypeAPI>>} A promise that resolves to an AxiosResponse containing the validation results.
 */
export async function postValidatePrompt(
  name: string,
  template: string,
  frontend_node: APIClassType,
): Promise<AxiosResponse<PromptTypeAPI>> {
  return api.post(`${BASE_URL_API}validate/prompt`, {
    name,
    template,
    frontend_node,
  });
}

/**
 * Fetches a list of JSON files from a GitHub repository and returns their contents as an array of FlowType objects.
 *
 * @returns {Promise<FlowType[]>} A promise that resolves to an array of FlowType objects.
 */
export async function getExamples(): Promise<FlowType[]> {
  const url =
    "https://api.github.com/repos/langflow-ai/langflow_examples/contents/examples?ref=main";
  const response = await api.get(url);

  const jsonFiles = response.data.filter((file: any) => {
    return file.name.endsWith(".json");
  });

  const contentsPromises = jsonFiles.map(async (file: any) => {
    const contentResponse = await api.get(file.download_url);
    return contentResponse.data;
  });

  return await Promise.all(contentsPromises);
}

/**
 * Saves a new flow to the database.
 *
 * @param {FlowType} newFlow - The flow data to save.
 * @returns {Promise<any>} The saved flow data.
 * @throws Will throw an error if saving fails.
 */
export async function saveFlowToDatabase(newFlow: {
  name: string;
  id: string;
  data: ReactFlowJsonObject | null;
  description: string;
  style?: FlowStyleType;
  is_component?: boolean;
  folder_id?: string;
  endpoint_name?: string;
}): Promise<FlowType> {
  try {
    const response = await api.post(`${BASE_URL_API}flows/`, {
      name: newFlow.name,
      data: newFlow.data,
      description: newFlow.description,
      is_component: newFlow.is_component,
      folder_id: newFlow.folder_id === "" ? null : newFlow.folder_id,
      endpoint_name: newFlow.endpoint_name,
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}
/**
 * Updates an existing flow in the database.
 *
 * @param {FlowType} updatedFlow - The updated flow data.
 * @returns {Promise<any>} The updated flow data.
 * @throws Will throw an error if the update fails.
 */
export async function updateFlowInDatabase(
  updatedFlow: FlowType,
): Promise<FlowType> {
  try {
    const response = await api.patch(`${BASE_URL_API}flows/${updatedFlow.id}`, {
      name: updatedFlow.name,
      data: updatedFlow.data,
      description: updatedFlow.description,
      folder_id: updatedFlow.folder_id === "" ? null : updatedFlow.folder_id,
      endpoint_name: updatedFlow.endpoint_name,
    });

    if (response?.status !== 200) {
      throw new Error(`HTTP error! status: ${response?.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Reads all flows from the database.
 *
 * @returns {Promise<any>} The flows data.
 * @throws Will throw an error if reading fails.
 */
export async function readFlowsFromDatabase() {
  try {
    const response = await api.get(`${BASE_URL_API}flows/`);
    if (response?.status !== 200) {
      throw new Error(`HTTP error! status: ${response?.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function downloadFlowsFromDatabase() {
  try {
    const response = await api.get(`${BASE_URL_API}flows/download/`);
    if (response?.status !== 200) {
      throw new Error(`HTTP error! status: ${response?.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function uploadFlowsToDatabase(flows: FormData) {
  try {
    const response = await api.post(`${BASE_URL_API}flows/upload/`, flows);

    if (response?.status !== 201) {
      throw new Error(`HTTP error! status: ${response?.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Deletes a flow from the database.
 *
 * @param {string} flowId - The ID of the flow to delete.
 * @returns {Promise<any>} The deleted flow data.
 * @throws Will throw an error if deletion fails.
 */
export async function deleteFlowFromDatabase(flowId: string) {
  try {
    const response = await api.delete(`${BASE_URL_API}flows/${flowId}`);
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches a flow from the database by ID.
 *
 * @param {number} flowId - The ID of the flow to fetch.
 * @returns {Promise<any>} The flow data.
 * @throws Will throw an error if fetching fails.
 */
export async function getFlowFromDatabase(flowId: number) {
  try {
    const response = await api.get(`${BASE_URL_API}flows/${flowId}`);
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches flow styles from the database.
 *
 * @returns {Promise<any>} The flow styles data.
 * @throws Will throw an error if fetching fails.
 */
export async function getFlowStylesFromDatabase() {
  try {
    const response = await api.get(`${BASE_URL_API}flow_styles/`);
    if (response.status !== 200) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Saves a new flow style to the database.
 *
 * @param {FlowStyleType} flowStyle - The flow style data to save.
 * @returns {Promise<any>} The saved flow style data.
 * @throws Will throw an error if saving fails.
 */
export async function saveFlowStyleToDatabase(flowStyle: FlowStyleType) {
  try {
    const response = await api.post(`${BASE_URL_API}flow_styles/`, flowStyle, {
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches the version of the API.
 *
 * @returns {Promise<AxiosResponse<any>>} A promise that resolves to an AxiosResponse containing the version information.
 */
export async function getVersion() {
  const response = await api.get(`${BASE_URL_API}version`);
  return response.data;
}

/**
 * Fetches the build status of a flow.
 * @param {string} flowId - The ID of the flow to fetch the build status for.
 * @returns {Promise<BuildStatusTypeAPI>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function getBuildStatus(
  flowId: string,
): Promise<AxiosResponse<BuildStatusTypeAPI>> {
  return await api.get(`${BASE_URL_API}build/${flowId}/status`);
}

//docs for postbuildinit
/**
 * Posts the build init of a flow.
 * @param {string} flowId - The ID of the flow to fetch the build status for.
 * @returns {Promise<InitTypeAPI>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function postBuildInit(
  flow: FlowType,
): Promise<AxiosResponse<InitTypeAPI>> {
  return await api.post(`${BASE_URL_API}build/init/${flow.id}`, flow);
}

// fetch(`/upload/${id}`, {
//   method: "POST",
//   body: formData,
// });
/**
 * Uploads a file to the server.
 * @param {File} file - The file to upload.
 * @param {string} id - The ID of the flow to upload the file to.
 */
export async function uploadFile(
  file: File,
  id: string,
): Promise<AxiosResponse<UploadFileTypeAPI>> {
  const formData = new FormData();
  formData.append("file", file);
  return await api.post(`${BASE_URL_API}files/upload/${id}`, formData);
}

export async function getProfilePictures(): Promise<ProfilePicturesTypeAPI | null> {
  try {
    const res = await api.get(`${BASE_URL_API}files/profile_pictures/list`);

    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
  return null;
}

export async function postCustomComponent(
  code: string,
  apiClass: APIClassType,
): Promise<AxiosResponse<CustomComponentRequest>> {
  // let template = apiClass.template;
  return await api.post(`${BASE_URL_API}custom_component`, {
    code,
    frontend_node: apiClass,
  });
}

export async function postCustomComponentUpdate(
  code: string,
  template: APITemplateType,
  field: string,
  field_value: any,
): Promise<AxiosResponse<APIClassType>> {
  return await api.post(`${BASE_URL_API}custom_component/update`, {
    code,
    template,
    field,
    field_value,
  });
}

export async function onLogin(user: LoginType) {
  try {
    const response = await api.post(
      `${BASE_URL_API}login`,
      new URLSearchParams({
        username: user.username,
        password: user.password,
      }).toString(),
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      },
    );

    if (response.status === 200) {
      const data = response.data;
      return data;
    }
  } catch (error) {
    throw error;
  }
}

export async function autoLogin(abortSignal) {
  try {
    const response = await api.get(`${BASE_URL_API}auto_login`, {
      signal: abortSignal,
    });

    if (response.status === 200) {
      const data = response.data;
      return data;
    }
  } catch (error) {
    throw error;
  }
}

export async function renewAccessToken() {
  try {
    return await api.post(`${BASE_URL_API}refresh`);
  } catch (error) {
    throw error;
  }
}

export async function getLoggedUser(): Promise<Users | null> {
  try {
    const res = await api.get(`${BASE_URL_API}users/whoami`);

    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
  return null;
}

export async function addUser(user: UserInputType): Promise<Array<Users>> {
  try {
    const res = await api.post(`${BASE_URL_API}users/`, user);
    if (res.status !== 201) {
      throw new Error(res.data.detail);
    }
    return res.data;
  } catch (error) {
    throw error;
  }
}

export async function getUsersPage(
  skip: number,
  limit: number,
): Promise<Array<Users>> {
  try {
    const res = await api.get(
      `${BASE_URL_API}users/?skip=${skip}&limit=${limit}`,
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
  return [];
}

export async function deleteUser(user_id: string) {
  try {
    const res = await api.delete(`${BASE_URL_API}users/${user_id}`);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function updateUser(user_id: string, user: changeUser) {
  try {
    const res = await api.patch(`${BASE_URL_API}users/${user_id}`, user);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function resetPassword(user_id: string, user: resetPasswordType) {
  try {
    const res = await api.patch(
      `${BASE_URL_API}users/${user_id}/reset-password`,
      user,
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function getApiKey() {
  try {
    const res = await api.get(`${BASE_URL_API}api_key/`);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function createApiKey(name: string) {
  try {
    const res = await api.post(`${BASE_URL_API}api_key/`, { name });
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function deleteApiKey(api_key: string) {
  try {
    const res = await api.delete(`${BASE_URL_API}api_key/${api_key}`);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function addApiKeyStore(key: string) {
  try {
    const res = await api.post(`${BASE_URL_API}api_key/store`, {
      api_key: key,
    });
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

/**
 * Saves a new flow to the database.
 *
 * @param {FlowType} newFlow - The flow data to save.
 * @returns {Promise<any>} The saved flow data.
 * @throws Will throw an error if saving fails.
 */
export async function saveFlowStore(
  newFlow: {
    name?: string;
    data: ReactFlowJsonObject | null;
    description?: string;
    style?: FlowStyleType;
    is_component?: boolean;
    parent?: string;
    last_tested_version?: string;
  },
  tags: string[],
  publicFlow = false,
): Promise<FlowType> {
  try {
    const response = await api.post(`${BASE_URL_API}store/components/`, {
      name: newFlow.name,
      data: newFlow.data,
      description: newFlow.description,
      is_component: newFlow.is_component,
      parent: newFlow.parent,
      tags: tags,
      private: !publicFlow,
      status: publicFlow ? "Public" : "Private",
      last_tested_version: newFlow.last_tested_version,
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

/**
 * Fetches the flows from the store.
 * @returns {Promise<>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function getFlowsStore(): Promise<AxiosResponse<FlowType[]>> {
  return await api.get(`${BASE_URL_API}store/`);
}

export async function getStoreComponents({
  component_id = null,
  page = 1,
  limit = 9999999,
  is_component = null,
  sort = "-count(liked_by)",
  tags = [] || null,
  liked = null,
  isPrivate = null,
  search = null,
  filterByUser = null,
  fields = null,
}: {
  component_id?: string | null;
  page?: number;
  limit?: number;
  is_component?: boolean | null;
  sort?: string;
  tags?: string[] | null;
  liked?: boolean | null;
  isPrivate?: boolean | null;
  search?: string | null;
  filterByUser?: boolean | null;
  fields?: Array<string> | null;
}): Promise<StoreComponentResponse | undefined> {
  try {
    let url = `${BASE_URL_API}store/components/`;
    const queryParams: any = [];
    if (component_id !== undefined && component_id !== null) {
      queryParams.push(`component_id=${component_id}`);
    }
    if (search !== undefined && search !== null) {
      queryParams.push(`search=${search}`);
    }
    if (isPrivate !== undefined && isPrivate !== null) {
      queryParams.push(`private=${isPrivate}`);
    }
    if (tags !== undefined && tags !== null && tags.length > 0) {
      queryParams.push(`tags=${tags.join(encodeURIComponent(","))}`);
    }
    if (fields !== undefined && fields !== null && fields.length > 0) {
      queryParams.push(`fields=${fields.join(encodeURIComponent(","))}`);
    }

    if (sort !== undefined && sort !== null) {
      queryParams.push(`sort=${sort}`);
    } else {
      queryParams.push(`sort=-count(liked_by)`); // default sort
    }

    if (liked !== undefined && liked !== null) {
      queryParams.push(`liked=${liked}`);
    }

    if (filterByUser !== undefined && filterByUser !== null) {
      queryParams.push(`filter_by_user=${filterByUser}`);
    }

    if (page !== undefined) {
      queryParams.push(`page=${page ?? 1}`);
    }
    if (limit !== undefined) {
      queryParams.push(`limit=${limit ?? 9999999}`);
    }
    if (is_component !== null && is_component !== undefined) {
      queryParams.push(`is_component=${is_component}`);
    }
    if (queryParams.length > 0) {
      url += `?${queryParams.join("&")}`;
    }

    const res = await api.get(url);

    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function postStoreComponents(component: Component) {
  try {
    const res = await api.post(`${BASE_URL_API}store/components/`, component);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function getComponent(component_id: string) {
  try {
    const res = await api.get(
      `${BASE_URL_API}store/components/${component_id}`,
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function searchComponent(
  query: string | null,
  page?: number | null,
  limit?: number | null,
  status?: string | null,
  tags?: string[],
): Promise<StoreComponentResponse | undefined> {
  try {
    let url = `${BASE_URL_API}store/components/`;
    const queryParams: any = [];
    if (query !== undefined && query !== null) {
      queryParams.push(`search=${query}`);
    }
    if (page !== undefined && page !== null) {
      queryParams.push(`page=${page}`);
    }
    if (limit !== undefined && limit !== null) {
      queryParams.push(`limit=${limit}`);
    }
    if (status !== undefined && status !== null) {
      queryParams.push(`status=${status}`);
    }
    if (tags !== undefined && tags !== null) {
      queryParams.push(`tags=${tags}`);
    }
    if (queryParams.length > 0) {
      url += `?${queryParams.join("&")}`;
    }

    const res = await api.get(url);

    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function checkHasApiKey() {
  try {
    const res = await api.get(`${BASE_URL_API}store/check/api_key`);
    if (res?.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function checkHasStore() {
  try {
    const res = await api.get(`${BASE_URL_API}store/check/`);
    if (res?.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function getCountComponents(is_component?: boolean | null) {
  try {
    let url = `${BASE_URL_API}store/components/count`;
    const queryParams: any = [];
    if (is_component !== undefined) {
      queryParams.push(`is_component=${is_component}`);
    }

    if (queryParams.length > 0) {
      url += `?${queryParams.join("&")}`;
    }

    const res = await api.get(url);

    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export async function getStoreTags() {
  try {
    const res = await api.get(`${BASE_URL_API}store/tags`);
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

export const postLikeComponent = (componentId: string) => {
  return api.post(`${BASE_URL_API}store/users/likes/${componentId}`);
};

/**
 * Updates an existing flow in the Store.
 *
 * @param {FlowType} updatedFlow - The updated flow data.
 * @returns {Promise<any>} The updated flow data.
 * @throws Will throw an error if the update fails.
 */
export async function updateFlowStore(
  newFlow: {
    name?: string;
    data: ReactFlowJsonObject | null;
    description?: string;
    style?: FlowStyleType;
    is_component?: boolean;
    parent?: string;
    last_tested_version?: string;
  },
  tags: string[],
  publicFlow = false,
  id: string,
): Promise<FlowType> {
  try {
    const response = await api.patch(`${BASE_URL_API}store/components/${id}`, {
      name: newFlow.name,
      data: newFlow.data,
      description: newFlow.description,
      is_component: newFlow.is_component,
      parent: newFlow.parent,
      tags: tags,
      private: !publicFlow,
      last_tested_version: newFlow.last_tested_version,
    });

    if (response.status !== 201) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function requestLogout() {
  try {
    const response = await api.post(`${BASE_URL_API}logout`);
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function getGlobalVariables(): Promise<{
  [key: string]: { id: string; type: string; default_fields: string[] };
}> {
  const globalVariables = {};
  (await api.get(`${BASE_URL_API}variables/`)).data.forEach((element) => {
    globalVariables[element.name] = {
      id: element.id,
      type: element.type,
      default_fields: element.default_fields,
    };
  });
  return globalVariables;
}

export async function registerGlobalVariable({
  name,
  value,
  type,
  default_fields = [],
}: {
  name: string;
  value: string;
  type?: string;
  default_fields?: string[];
}): Promise<AxiosResponse<{ name: string; id: string; type: string }>> {
  try {
    const response = await api.post(`${BASE_URL_API}variables/`, {
      name,
      value,
      type,
      default_fields: default_fields,
    });
    return response;
  } catch (error) {
    throw error;
  }
}

export async function deleteGlobalVariable(id: string) {
  try {
    const response = await api.delete(`${BASE_URL_API}variables/${id}`);
    return response;
  } catch (error) {
    throw error;
  }
}

export async function updateGlobalVariable(
  name: string,
  value: string,
  id: string,
) {
  try {
    const response = api.patch(`${BASE_URL_API}variables/${id}`, {
      name,
      value,
    });

    return response;
  } catch (error) {
    throw error;
  }
}

export async function getVerticesOrder(
  flowId: string,
  startNodeId?: string | null,
  stopNodeId?: string | null,
  nodes?: Node[],
  Edges?: Edge[],
): Promise<AxiosResponse<VerticesOrderTypeAPI>> {
  // nodeId is optional and is a query parameter
  // if nodeId is not provided, the API will return all vertices
  const config: AxiosRequestConfig<any> = {};
  if (stopNodeId) {
    config["params"] = { stop_component_id: stopNodeId };
  } else if (startNodeId) {
    config["params"] = { start_component_id: startNodeId };
  }
  const data = {
    data: {},
  };
  if (nodes && Edges) {
    data["data"]["nodes"] = nodes;
    data["data"]["edges"] = Edges;
  }
  return await api.post(
    `${BASE_URL_API}build/${flowId}/vertices`,
    data,
    config,
  );
}

export async function postBuildVertex(
  flowId: string,
  vertexId: string,
  input_value: string,
  files?: string[],
): Promise<AxiosResponse<VertexBuildTypeAPI>> {
  // input_value is optional and is a query parameter
  let data = {};
  if (typeof input_value !== "undefined") {
    data["inputs"] = { input_value: input_value };
  }
  if (data && files) {
    data["files"] = files;
  }
  return await api.post(
    `${BASE_URL_API}build/${flowId}/vertices/${vertexId}`,
    data,
  );
}

export async function downloadImage({ flowId, fileName }): Promise<any> {
  return await api.get(`${BASE_URL_API}files/images/${flowId}/${fileName}`);
}

export async function getFlowPool({
  flowId,
  nodeId,
}: {
  flowId: string;
  nodeId?: string;
}): Promise<AxiosResponse<{ vertex_builds: FlowPoolType }>> {
  const config = {};
  config["params"] = { flow_id: flowId };
  if (nodeId) {
    config["params"] = { nodeId };
  }
  return await api.get(`${BASE_URL_API}monitor/builds`, config);
}

export async function deleteFlowPool(
  flowId: string,
): Promise<AxiosResponse<any>> {
  const config = {};
  config["params"] = { flow_id: flowId };
  return await api.delete(`${BASE_URL_API}monitor/builds`, config);
}

/**
 * Deletes multiple flow components by their IDs.
 * @param flowIds - An array of flow IDs to be deleted.
 * @param token - The authorization token for the API request.
 * @returns A promise that resolves to an array of AxiosResponse objects representing the delete responses.
 */
export async function multipleDeleteFlowsComponents(
  flowIds: string[],
): Promise<AxiosResponse<any>[]> {
  const batches: string[][] = [];

  // Split the flowIds into batches
  for (let i = 0; i < flowIds.length; i += MAX_BATCH_SIZE) {
    batches.push(flowIds.slice(i, i + MAX_BATCH_SIZE));
  }

  // Function to delete a batch of flow IDs
  const deleteBatch = async (batch: string[]): Promise<AxiosResponse<any>> => {
    try {
      return await api.delete(`${BASE_URL_API}flows/`, {
        data: batch,
      });
    } catch (error) {
      console.error("Error deleting flows:", error);
      throw error;
    }
  };

  // Execute all delete requests
  const responses: Promise<AxiosResponse<any>>[] = batches.map((batch) =>
    deleteBatch(batch),
  );

  // Return the responses after all requests are completed
  return Promise.all(responses);
}

export async function getTransactionTable(
  id: string,
  mode: "intersection" | "union",
  params = {},
): Promise<{ rows: Array<object>; columns: Array<ColDef | ColGroupDef> }> {
  const config = {};
  config["params"] = { flow_id: id };
  if (params) {
    config["params"] = { ...config["params"], ...params };
  }
  const rows = await api.get(`${BASE_URL_API}monitor/transactions`, config);
  const columns = extractColumnsFromRows(rows.data, mode);
  return { rows: rows.data, columns };
}

export async function deleteMessagesFn(ids: string[]) {
  try {
    return await api.delete(`${BASE_URL_API}monitor/messages`, {
      data: ids,
    });
  } catch (error) {
    console.error("Error deleting flows:", error);
    throw error;
  }
}

export async function updateMessageApi(data: Message) {
  if (data.files && typeof data.files === "string") {
    data.files = JSON.parse(data.files);
  }
  return await api.put(`${BASE_URL_API}monitor/messages/${data.id}`, data);
}
