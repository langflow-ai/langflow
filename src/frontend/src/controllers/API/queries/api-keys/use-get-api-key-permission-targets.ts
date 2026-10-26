import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ApiKeyPermissionTarget {
  id: string;
  name: string;
}

interface TargetRecord {
  id: string;
  name?: string;
  display_name?: string;
  dir_name?: string;
  resource_type?: string;
  resource_id?: string;
}

const target = (row: TargetRecord): ApiKeyPermissionTarget => ({
  id: row.id,
  name:
    row.display_name || row.name || row.dir_name || row.resource_id || row.id,
});

async function providerAccounts(): Promise<TargetRecord[]> {
  const rows: TargetRecord[] = [];
  let total = 0;
  let page = 1;
  do {
    const { data } = await api.get<{
      provider_accounts: TargetRecord[];
      total: number;
    }>(getURL("DEPLOYMENT_PROVIDER_ACCOUNTS"), { params: { page, size: 50 } });
    rows.push(...data.provider_accounts);
    total = data.total;
    page += 1;
    if (!data.provider_accounts.length) break;
  } while (rows.length < total);
  return rows;
}

export async function getApiKeyPermissionTargets(
  resourceType: string,
): Promise<ApiKeyPermissionTarget[]> {
  let records: TargetRecord[];
  switch (resourceType) {
    case "project":
      records = (await api.get<TargetRecord[]>(`${getURL("PROJECTS")}/`)).data;
      break;
    case "flow": {
      const { data } = await api.get<
        TargetRecord[] | { items: TargetRecord[] }
      >(`${getURL("FLOWS")}/`, {
        params: { get_all: true, header_flows: true },
      });
      records = Array.isArray(data) ? data : data.items;
      break;
    }
    case "deployment": {
      records = [];
      for (const provider of await providerAccounts()) {
        let page = 1;
        let count = 0;
        let total = 0;
        do {
          const { data } = await api.get<{
            deployments: TargetRecord[];
            total: number;
          }>(getURL("DEPLOYMENTS"), {
            params: { provider_id: provider.id, page, size: 50 },
          });
          records.push(...data.deployments);
          count += data.deployments.length;
          total = data.total;
          page += 1;
          if (!data.deployments.length) break;
        } while (count < total);
      }
      break;
    }
    case "provider_account":
      records = await providerAccounts();
      break;
    case "variable":
      records = (await api.get<TargetRecord[]>(`${getURL("VARIABLES")}/`)).data;
      break;
    case "file":
      records = (
        await api.get<TargetRecord[]>(getURL("FILE_MANAGEMENT", {}, true))
      ).data;
      break;
    case "knowledge_base":
      records = (await api.get<TargetRecord[]>(`${getURL("KNOWLEDGE_BASES")}/`))
        .data;
      break;
    case "connection":
      records = (await api.get<TargetRecord[]>(getURL("CONNECTIONS"))).data;
      break;
    case "share": {
      records = [];
      let page: TargetRecord[];
      do {
        page = (
          await api.get<TargetRecord[]>(getURL("AUTHZ_SHARES"), {
            params: { limit: 200, offset: records.length },
          })
        ).data;
        records.push(...page);
      } while (page.length === 200);
      break;
    }
    default:
      return [];
  }
  return records.map(target);
}

export const useGetApiKeyPermissionTargets: useQueryFunctionType<
  { resourceType: string },
  ApiKeyPermissionTarget[]
> = ({ resourceType }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetApiKeyPermissionTargets", resourceType],
    () => getApiKeyPermissionTargets(resourceType),
    { retry: false, ...options },
  );
};
