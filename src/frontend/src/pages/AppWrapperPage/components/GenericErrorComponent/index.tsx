import TimeoutErrorComponent from "@/components/common/timeoutErrorComponent";
import { useTranslation } from "react-i18next";
import CustomFetchErrorComponent from "@/customization/components/custom-fetch-error-component";

export function GenericErrorComponent({ healthCheckTimeout, fetching, retry }) {
  const { t } = useTranslation();
  switch (healthCheckTimeout) {
    case "serverDown":
      return (
        <CustomFetchErrorComponent
          description={t("misc.fetchErrorDescription")}
          message={t("misc.fetchErrorMessage")}
          openModal={true}
          setRetry={retry}
          isLoadingHealth={fetching}
        ></CustomFetchErrorComponent>
      );
    case "timeout":
      return (
        <TimeoutErrorComponent
          description={t("misc.timeoutErrorMessage")}
          message={t("misc.timeoutErrorDescription")}
          openModal={true}
          setRetry={retry}
          isLoadingHealth={fetching}
        ></TimeoutErrorComponent>
      );
    default:
      return <></>;
  }
}
