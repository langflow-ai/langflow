import { AxiosResponse } from "axios";
import { ReactFlowJsonObject } from "reactflow";
import { BASE_URL_API } from "../../constants/constants";
import { api } from "../../controllers/API/api";
import {
  APIObjectType,
  Component,
  LoginType,
  Users,
  changeUser,
  resetPasswordType,
  sendAllProps,
} from "../../types/api/index";
import { UserInputType } from "../../types/components";
import { FlowStyleType, FlowType } from "../../types/flow";
import { StoreComponentResponse } from "../../types/store";
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
 * @returns {Promise<AxiosResponse<APIObjectType>>} A promise that resolves to an AxiosResponse containing all the objects.
 */
export async function getAll(): Promise<AxiosResponse<APIObjectType>> {
  return await api.get(`${BASE_URL_API}all`);
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
  code: string
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
  frontend_node: APIClassType
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
    "https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples?ref=main";
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
}): Promise<FlowType> {
  try {
    const response = await api.post(`${BASE_URL_API}flows/`, {
      name: newFlow.name,
      data: newFlow.data,
      description: newFlow.description,
      is_component: newFlow.is_component,
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
  updatedFlow: FlowType
): Promise<FlowType> {
  try {
    const response = await api.patch(`${BASE_URL_API}flows/${updatedFlow.id}`, {
      name: updatedFlow.name,
      data: updatedFlow.data,
      description: updatedFlow.description,
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
  const respnose = await api.get(`${BASE_URL_API}version`);
  return respnose.data;
}

/**
 * Fetches the health status of the API.
 *
 * @returns {Promise<AxiosResponse<any>>} A promise that resolves to an AxiosResponse containing the health status.
 */
export async function getHealth() {
  return await api.get("/health"); // Health is the only endpoint that doesn't require /api/v1
}

/**
 * Fetches the build status of a flow.
 * @param {string} flowId - The ID of the flow to fetch the build status for.
 * @returns {Promise<BuildStatusTypeAPI>} A promise that resolves to an AxiosResponse containing the build status.
 *
 */
export async function getBuildStatus(
  flowId: string
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
  flow: FlowType
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
  id: string
): Promise<AxiosResponse<UploadFileTypeAPI>> {
  const formData = new FormData();
  formData.append("file", file);
  return await api.post(`${BASE_URL_API}upload/${id}`, formData);
}

export async function postCustomComponent(
  code: string,
  apiClass: APIClassType
): Promise<AxiosResponse<APIClassType>> {
  // let template = apiClass.template;
  return await api.post(`${BASE_URL_API}custom_component`, {
    code,
    frontend_node: apiClass,
  });
}

export async function postCustomComponentUpdate(
  code: string,
  field: string
): Promise<AxiosResponse<APIClassType>> {
  return await api.post(`${BASE_URL_API}custom_component/update`, {
    code,
    field,
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
      }
    );

    if (response.status === 200) {
      const data = response.data;
      return data;
    }
  } catch (error) {
    throw error;
  }
}

export async function autoLogin() {
  try {
    const response = await api.get(`${BASE_URL_API}auto_login`);

    if (response.status === 200) {
      const data = response.data;
      return data;
    }
  } catch (error) {
    throw error;
  }
}

export async function renewAccessToken(token: string) {
  try {
    if (token) {
      return await api.post(`${BASE_URL_API}refresh?token=${token}`);
    }
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
    console.log("Error:", error);
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
    console.log("Error:", error);
    throw error;
  }
}

export async function getUsersPage(
  skip: number,
  limit: number
): Promise<Array<Users>> {
  try {
    const res = await api.get(
      `${BASE_URL_API}users/?skip=${skip}&limit=${limit}`
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
    throw error;
  }
}

export async function resetPassword(user_id: string, user: resetPasswordType) {
  try {
    const res = await api.patch(
      `${BASE_URL_API}users/${user_id}/reset-password`,
      user
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
  publicFlow = false
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
    console.log("Error:", error);
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
    console.log("Error:", error);
    throw error;
  }
}

export async function getComponent(component_id: string) {
  try {
    const res = await api.get(
      `${BASE_URL_API}store/components/${component_id}`
    );
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    console.log("Error:", error);
    throw error;
  }
}

export async function searchComponent(
  query: string | null,
  page?: number | null,
  limit?: number | null,
  status?: string | null,
  tags?: string[]
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
    console.log("Error:", error);
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
  id: string
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
