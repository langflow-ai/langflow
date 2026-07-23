import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import {
  type AvailableDBProviderId,
  DB_PROVIDER_OPTIONS,
  type DBProviderConfigField,
  type DBProviderId,
  type DBProviderOption,
  type DBProviderTextField,
  toAPIBackendType,
} from "@/constants/dbProviderConstants";
import { useTestDBProviderConnection } from "@/controllers/API/queries/knowledge-bases/use-test-kb-connection";
import useAlertStore from "@/stores/alertStore";
import { buildBackendConfigPayload } from "../helpers/build-backend-config-payload";

type ApiError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

const getErrorDetail = (error: unknown) =>
  (error as ApiError)?.response?.data?.detail ||
  "An unexpected error occurred. Please try again.";

/**
 * Save / Test Connection / Use Chroma flows for the DB Providers page.
 * Pure orchestration over the variable primitives and field resolution
 * owned by the page — no rendering concerns.
 */
export function useDBProviderActions({
  selectedProvider,
  canSave,
  getFieldValue,
  variableValues,
  setVariable,
  activateProvider,
  setVariableValues,
  setEditingSecret,
  setHasManuallySelectedProvider,
  setSelectedProviderId,
}: {
  selectedProvider: DBProviderOption;
  canSave: boolean;
  getFieldValue: (field: DBProviderConfigField) => string;
  variableValues: Record<string, string>;
  setVariable: (params: {
    name: string;
    value: string;
    isSecret: boolean;
  }) => Promise<void>;
  activateProvider: (provider: DBProviderOption) => Promise<void>;
  setVariableValues: Dispatch<SetStateAction<Record<string, string>>>;
  setEditingSecret: Dispatch<SetStateAction<Record<string, boolean>>>;
  setHasManuallySelectedProvider: Dispatch<SetStateAction<boolean>>;
  setSelectedProviderId: Dispatch<SetStateAction<DBProviderId>>;
}) {
  const { t } = useTranslation();
  const { mutateAsync: testProviderConnection, isPending: isTesting } =
    useTestDBProviderConnection();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Returns ``true`` if the save fully succeeded so callers (the Test
  // Connection button) can chain a follow-up step. Errors are surfaced
  // via toast inside the function — callers should not duplicate them.
  //
  // ``skipActivation`` lets the Test Connection flow persist credentials
  // (so server-side variable_service can resolve them) without switching
  // the active provider — testing should never silently change settings.
  const handleSave = async (options?: {
    silent?: boolean;
    skipActivation?: boolean;
  }): Promise<boolean> => {
    if (selectedProvider.status !== "available") return false;
    if (!canSave) {
      setErrorData({
        title: t("settings.dbProviders.errorMissingConfig"),
        list: [
          `${selectedProvider.label} requires ${selectedProvider.configFields
            .filter(
              (field): field is DBProviderTextField =>
                field.kind !== "boolean" &&
                field.required &&
                !getFieldValue(field).trim(),
            )
            .map((field) => field.label)
            .join(", ")}.`,
        ],
      });
      return false;
    }

    try {
      const fieldsToSave = selectedProvider.configFields.filter((field) => {
        if (field.kind === "boolean") {
          // Persist booleans only when the user actually flipped them
          // this session — otherwise we'd write the default to a
          // global variable on every save, polluting the variables
          // page with values the user never set.
          return field.variableKey in variableValues;
        }
        const nextValue = getFieldValue(field).trim();
        return (
          nextValue && (field.variableKey in variableValues || field.required)
        );
      });

      await Promise.all(
        fieldsToSave.map((field) => {
          const value =
            field.kind === "boolean"
              ? getFieldValue(field) // already "true" / "false"
              : getFieldValue(field).trim();
          return setVariable({
            name: field.variableKey,
            value,
            isSecret: field.kind === "boolean" ? false : field.isSecret,
          });
        }),
      );
      if (!options?.skipActivation) {
        await activateProvider(selectedProvider);
        // Resetting these on a non-activating save would re-snap the
        // selected panel back to the active provider via the
        // ``activeProviderId`` useEffect — that's correct after a real
        // Save, but wrong when we're only persisting credentials for
        // a Test Connection round-trip on a non-active provider.
        setVariableValues({});
        setEditingSecret({});
        setHasManuallySelectedProvider(false);
      }
      if (!options?.silent) {
        setSuccessData({
          title:
            selectedProvider.id === "chroma"
              ? t("settings.dbProviders.chromaSelected")
              : t("settings.dbProviders.configSaved", {
                  provider: selectedProvider.label,
                }),
        });
      }
      return true;
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorSaving"),
        list: [getErrorDetail(error)],
      });
      return false;
    }
  };

  const handleTestConnection = async () => {
    if (selectedProvider.status !== "available") return;
    if (!canSave) {
      setErrorData({
        title: t("settings.dbProviders.errorMissingConfig"),
        list: [
          `${selectedProvider.label} requires ${selectedProvider.configFields
            .filter(
              (field): field is DBProviderTextField =>
                field.kind !== "boolean" &&
                field.required &&
                !getFieldValue(field).trim(),
            )
            .map((field) => field.label)
            .join(", ")}.`,
        ],
      });
      return;
    }

    // Build the test payload from current form state BEFORE saving —
    // ``handleSave`` clears ``variableValues`` on success, so reading
    // form values afterward would surface stale globals instead of the
    // user's just-saved draft. The backend_config still references
    // credential VARIABLE NAMES (URL/USERNAME/PASSWORD), so the
    // server-side variable_service lookup happens after Save persists
    // them.
    const literalFields: Record<string, string> = {};
    const booleanFields: Record<string, boolean> = {};
    for (const field of selectedProvider.configFields) {
      const raw = getFieldValue(field);
      if (field.kind === "boolean") {
        booleanFields[field.variableKey] = raw === "true";
      } else {
        literalFields[field.variableKey] = raw.trim();
      }
    }

    // Persist the variables first; the server-side test reads
    // OPENSEARCH_URL etc. through ``variable_service``. Skip the
    // activation step — testing must not switch the active provider.
    const saved = await handleSave({ silent: true, skipActivation: true });
    if (!saved) {
      // ``handleSave`` already surfaced an error toast.
      return;
    }

    try {
      const backendConfig = buildBackendConfigPayload(
        selectedProvider.id as AvailableDBProviderId,
        literalFields,
        booleanFields,
      );
      const response = await testProviderConnection({
        backend_type: toAPIBackendType(
          selectedProvider.id as AvailableDBProviderId,
        ),
        backend_config: backendConfig,
      });
      if (response.ok) {
        // ``setSuccessData`` only takes a title; pack any backend
        // detail (cluster name, version) into the title so it shows.
        setSuccessData({
          title: response.message
            ? t("settings.dbProviders.connectionSuccessfulWith", {
                message: response.message,
              })
            : t("settings.dbProviders.connectionSuccessful"),
        });
      } else {
        setErrorData({
          title: t("settings.dbProviders.connectionFailed"),
          list: [
            response.message || t("settings.dbProviders.connectionRejected"),
          ],
        });
      }
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorTesting"),
        list: [getErrorDetail(error)],
      });
    }
  };

  const handleUseChroma = async () => {
    const chromaProvider = DB_PROVIDER_OPTIONS[0];
    try {
      await activateProvider(chromaProvider);
      setSelectedProviderId("chroma");
      setHasManuallySelectedProvider(false);
      setSuccessData({ title: t("settings.dbProviders.chromaSelected") });
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorSelectingChroma"),
        list: [getErrorDetail(error)],
      });
    }
  };

  return { handleSave, handleTestConnection, handleUseChroma, isTesting };
}
