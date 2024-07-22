import { useQueryFunctionType } from "@/types/api";
import { cloneDeep } from "lodash";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IMetadata {
  [char: string]:
    | {
        count: number;
      }
    | number;
}

interface ITags {
  id: string;
  name: string;
}

interface IComponentData {
  id: string;
  name: string;
  description: string;
  liked_by_count: number;
  liked_by_user: undefined | boolean;
  is_component: boolean;
  metadata: IMetadata;
  user_created: {
    username: string;
  };
  tags: Array<ITags>;
  downloads_count: number;
  last_tested_version: string;
  private: boolean;
}

type componentsQueryResponse = {
  count: number;
  authorized: boolean;
  results: Array<IComponentData>;
};

interface IGetComponentsParams {
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
}

export const useGetStoreComponentsQuery: useQueryFunctionType<
  IGetComponentsParams,
  componentsQueryResponse
> = (
  {
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
  },
  options,
) => {
  const { query } = UseRequestProcessor();

  const processUrl = (url: string): string => {
    let newUrl = cloneDeep(url);
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
      newUrl += `?${queryParams.join("&")}`;
    }
    return newUrl;
  };

  const getComponentFn = async () => {
    const url = processUrl(`${getURL("STORE")}/components/`);
    return await api.get<componentsQueryResponse>(url);
  };

  const responseFn = async () => {
    const { data } = await getComponentFn();
    return data;
  };

  const queryResult = query(["useGetStoreComponentsQuery"], responseFn, {
    ...options,
  });

  return queryResult;
};
