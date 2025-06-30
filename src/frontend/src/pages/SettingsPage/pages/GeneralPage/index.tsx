import {
  EDIT_PASSWORD_ALERT_LIST,
  EDIT_PASSWORD_ERROR_ALERT,
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "@/constants/alerts_constants";
import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import {
  useResetPassword,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import { useGetProfilePicturesQuery } from "@/controllers/API/queries/files";
import { useGetCategoryVariable } from "@/controllers/API/queries/variables/use-get-categories";
import { usePatchGlobalVariables } from "@/controllers/API/queries/variables/use-patch-global-variables";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables/use-post-global-variables";
import { ENABLE_PROFILE_ICONS } from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { cloneDeep } from "lodash";
import { useContext, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CATEGORY_SETTINGS,
  CONTROL_PATCH_USER_STATE,
} from "../../../../constants/constants";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import { useStoreStore } from "../../../../stores/storeStore";
import {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../../../types/components";
import useScrollToElement from "../hooks/use-scroll-to-element";
import GeneralPageHeaderComponent from "./components/GeneralPageHeader";
import PasswordFormComponent from "./components/PasswordForm";
import ProfilePictureFormComponent from "./components/ProfilePictureForm";
import UsageDataFormComponent from "./components/usage-data/usage-data";

export const GeneralPage = () => {
  const { scrollId } = useParams();

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE,
  );

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const { password, cnfPassword, profilePicture } = inputState;
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const usageData = useGlobalVariablesStore((state) => state.usageData);
  const setUsageData = useGlobalVariablesStore((state) => state.setUsageData);

  const { mutate: mutateUsageData } = usePostGlobalVariables({
    onSuccess: () => {
      setSuccessData({ title: "Usage data saved successfully" });
    },
    onError: (error) => {
      setErrorData({
        title: "Usage data save error",
        list: [(error as any)?.response?.data?.detail],
      });
    },
  });

  const { mutate: mutatePatchUsageData } = usePatchGlobalVariables({
    onSuccess: () => {
      setSuccessData({ title: "Usage data saved successfully" });
    },
    onError: (error) => {
      setErrorData({
        title: "Usage data save error",
        list: [(error as any)?.response?.data?.detail],
      });
    },
  });

  const { data: usageDataQuery } = useGetCategoryVariable({
    category: CATEGORY_SETTINGS,
    variableName: "enable_telemetry",
  });

  useEffect(() => {
    if (usageDataQuery) {
      setUsageData(usageDataQuery);
    }
  }, [usageDataQuery]);

  const { mutate: mutateResetPassword } = useResetPassword();
  const { mutate: mutatePatchUser } = useUpdateUser();

  const handlePatchPassword = () => {
    if (password !== cnfPassword) {
      setErrorData({
        title: EDIT_PASSWORD_ERROR_ALERT,
        list: [EDIT_PASSWORD_ALERT_LIST],
      });
      return;
    }

    if (password !== "") {
      mutateResetPassword(
        { user_id: userData!.id, password: { password } },
        {
          onSuccess: () => {
            handleInput({ target: { name: "password", value: "" } });
            handleInput({ target: { name: "cnfPassword", value: "" } });
            setSuccessData({ title: SAVE_SUCCESS_ALERT });
          },
          onError: (error) => {
            setErrorData({
              title: SAVE_ERROR_ALERT,
              list: [(error as any)?.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  const handleGetProfilePictures = useGetProfilePicturesQuery();

  const handlePatchProfilePicture = (profile_picture) => {
    if (profile_picture !== "") {
      mutatePatchUser(
        { user_id: userData!.id, user: { profile_image: profile_picture } },
        {
          onSuccess: () => {
            let newUserData = cloneDeep(userData);
            newUserData!.profile_image = profile_picture;
            setUserData(newUserData);
            setSuccessData({ title: SAVE_SUCCESS_ALERT });
          },
          onError: (error) => {
            setErrorData({
              title: SAVE_ERROR_ALERT,
              list: [(error as any)?.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  useScrollToElement(scrollId);

  const { mutate } = usePostAddApiKey({
    onSuccess: () => {
      setSuccessData({ title: "API key saved successfully" });
      setHasApiKey(true);
      setValidApiKey(true);
      setLoadingApiKey(false);
      handleInput({ target: { name: "apikey", value: "" } });
    },
    onError: (error) => {
      setErrorData({
        title: "API key save error",
        list: [(error as any)?.response?.data?.detail],
      });
      setHasApiKey(false);
      setValidApiKey(false);
      setLoadingApiKey(false);
    },
  });

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  const handleSetUsageData = (usageValue: boolean) => {
    if (!usageData?.id) {
      mutateUsageData(
        {
          name: "enable_telemetry",
          value: usageValue === true ? "true" : "false",
          type: "generic",
          default_fields: [],
          category: CATEGORY_SETTINGS,
        },
        {
          onSuccess: (res) => {
            setUsageData(res);
          },
        },
      );
    } else {
      mutatePatchUsageData(
        {
          name: "enable_telemetry",
          value: usageValue === true ? "true" : "false",
          category: CATEGORY_SETTINGS,
          id: usageData?.id,
          type: "generic",
        },
        {
          onSuccess: (res) => {
            setSuccessData({ title: "Usage data saved successfully" });
            setUsageData(res);
          },
        },
      );
    }
  };

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <GeneralPageHeaderComponent />

      <div className="flex w-full flex-col gap-6">
        {ENABLE_PROFILE_ICONS && (
          <ProfilePictureFormComponent
            profilePicture={profilePicture}
            handleInput={handleInput}
            handlePatchProfilePicture={handlePatchProfilePicture}
            handleGetProfilePictures={handleGetProfilePictures}
            userData={userData}
          />
        )}

        {!autoLogin && (
          <PasswordFormComponent
            password={password}
            cnfPassword={cnfPassword}
            handleInput={handleInput}
            handlePatchPassword={handlePatchPassword}
          />
        )}

        <UsageDataFormComponent
          usageData={usageData?.value === "true"}
          setUsageData={handleSetUsageData}
        />
      </div>
    </div>
  );
};

export default GeneralPage;
