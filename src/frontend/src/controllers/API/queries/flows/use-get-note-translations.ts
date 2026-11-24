import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetNoteTranslationsQuery = (flowId: string | undefined) => {
  const { i18n } = useTranslation();
  const { query } = UseRequestProcessor();

  return query(
    ["noteTranslations", flowId, i18n.language],
    async () => {
      const { data } = await api.get<Record<string, string>>(
        `${getURL("FLOWS")}/${flowId}/note_translations`,
      );
      return data;
    },
    { enabled: !!flowId },
  );
};
