import type { Edge, Node, ReactFlowJsonObject } from "@xyflow/react";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import {
  customGetAppVersions,
  customGetLatestVersion,
} from "@/customization/utils/custom-get-app-latest-version";
import { BASE_URL_API } from "../../constants/constants";
import { api } from "../../controllers/API/api";
import type {
  VertexBuildTypeAPI,
  VerticesOrderTypeAPI,
} from "../../types/api/index";
import type { FlowStyleType, FlowType } from "../../types/flow";
import type { StoreComponentResponse } from "../../types/store";

const GITHUB_API_URL = "https://api.github.com";
const DISCORD_API_URL =
  "https://discord.com/api/v9/invites/EqksyE2EX9?with_counts=true";

export async function getRepoStars(owner: string, repo: string) {
  try {
    const response = await api.get(`${GITHUB_API_URL}/repos/${owner}/${repo}`);
    return response?.data.stargazers_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

export async function getDiscordCount() {
  try {
    const response = await api.get(DISCORD_API_URL);
    return response?.data.approximate_member_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

export const getAppVersions = customGetAppVersions;
export const getLatestVersion = customGetLatestVersion;

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
    return response?.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function getStoreComponents({
  component_id = null,
  page = 1,
  limit = 9999999,
  is_component = null,
  sort = "-count(liked_by)",
  tags = [],
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
    return response?.data;
  } catch (error) {
    console.error(error);
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
  const data = {};
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
