import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { buildPolicyBundleUpdate } from "./build-policy-bundle-update";
import type {
  PolicyBundleChanges,
  PolicyBundleRead,
  PolicyBundleWrite,
} from "./types";

export const policyBundleKeys = {
  all: ["policy-bundle"] as const,
  current: () => [...policyBundleKeys.all, "current"] as const,
} as const;

export async function getPolicyBundle(): Promise<PolicyBundleRead> {
  const { data } = await api.get<PolicyBundleRead>(getURL("POLICY_BUNDLE"));
  return data;
}

export async function replacePolicyBundle(
  payload: PolicyBundleWrite,
): Promise<PolicyBundleRead> {
  const { data } = await api.put<PolicyBundleRead>(
    getURL("POLICY_BUNDLE"),
    payload,
  );
  return data;
}

export const usePolicyBundleQuery = (enabled = true) =>
  useQuery<PolicyBundleRead>({
    queryKey: policyBundleKeys.current(),
    queryFn: getPolicyBundle,
    enabled,
    retry: 1,
  });

/**
 * Writes a change set against the bundle it was read from. The caller passes
 * only the lists it edits; the rest travel unchanged, so one panel never clears
 * another's decisions.
 */
export const useSavePolicyBundleMutation = () => {
  const client = useQueryClient();
  return useMutation<
    PolicyBundleRead,
    unknown,
    { bundle: PolicyBundleRead; changes: PolicyBundleChanges }
  >({
    mutationFn: ({ bundle, changes }) =>
      replacePolicyBundle(buildPolicyBundleUpdate(bundle, changes)),
    onSuccess: (saved) => {
      client.setQueryData(policyBundleKeys.current(), saved);
      client.invalidateQueries({ queryKey: policyBundleKeys.all });
    },
  });
};
