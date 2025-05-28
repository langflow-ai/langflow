import TimeoutErrorComponent from "@/components/common/timeoutErrorComponent";
import {
  FETCH_ERROR_DESCRIPION,
  FETCH_ERROR_MESSAGE,
  TIMEOUT_ERROR_DESCRIPION,
  TIMEOUT_ERROR_MESSAGE,
} from "@/constants/constants";
import CustomFetchErrorComponent from "@/customization/components/custom-fetch-error-component";

export function GenericErrorComponent({ healthCheckTimeout, fetching, retry }) {
  switch (healthCheckTimeout) {
    case "serverDown":
      return (
        <CustomFetchErrorComponent
          description={FETCH_ERROR_DESCRIPION}
          message={FETCH_ERROR_MESSAGE}
          openModal={true}
          setRetry={retry}
          isLoadingHealth={fetching}
        ></CustomFetchErrorComponent>
      );
    case "timeout":
      return (
        <TimeoutErrorComponent
          description={TIMEOUT_ERROR_MESSAGE}
          message={TIMEOUT_ERROR_DESCRIPION}
          openModal={true}
          setRetry={retry}
          isLoadingHealth={fetching}
        ></TimeoutErrorComponent>
      );
    default:
      return <></>;
  }
}
