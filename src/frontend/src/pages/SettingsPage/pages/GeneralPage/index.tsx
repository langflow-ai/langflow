import { cloneDeep } from "lodash";
import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import {
  useResetPassword,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import { useGetProfilePicturesQuery } from "@/controllers/API/queries/files";
import { CustomRegistrationData } from "@/customization/components/custom-registration-data";
import CustomSettingsPasswordFormGate from "@/customization/components/custom-settings-password-form-gate";
import { CustomTelemetryToggle } from "@/customization/components/custom-telemetry-toggle";
import { CustomTermsLinks } from "@/customization/components/custom-terms-links";
import { ENABLE_PROFILE_ICONS } from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { CONTROL_PATCH_USER_STATE } from "../../../../constants/constants";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import { useStoreStore } from "../../../../stores/storeStore";
import type {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../../../types/components";
import useScrollToElement from "../hooks/use-scroll-to-element";
import GeneralPageHeaderComponent from "./components/GeneralPageHeader";
import LanguageFormComponent from "./components/LanguageForm";
import PasswordFormComponent from "./components/PasswordForm";
import ProfilePictureFormComponent from "./components/ProfilePictureForm";

export const GeneralPage = () => {
  const { scrollId } = useParams();

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE,
  );
  // Password change rejection (mismatch or server error), mirrored inline so
  // the error is programmatically associated with the password fields
  // (WCAG 3.3.1) instead of living only in the transient toast.
  const [passwordFormError, setPasswordFormError] = useState<string | null>(
    null,
  );

  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const { currentPassword, password, cnfPassword, profilePicture } = inputState;
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const { storeApiKey } = useContext(AuthContext);
  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const { mutate: mutateResetPassword } = useResetPassword();
  const { mutate: mutatePatchUser } = useUpdateUser();

  const handlePatchPassword = () => {
    if (password !== cnfPassword) {
      setPasswordFormError(t("errors.passwordMismatch"));
      setErrorData({
        title: t("errors.changePassword"),
        list: [t("errors.passwordMismatch")],
      });
      return;
    }

    if (currentPassword !== "" && password !== "") {
      mutateResetPassword(
        {
          user_id: userData!.id,
          password: { current_password: currentPassword, password },
        },
        {
          onSuccess: () => {
            handleInput({ target: { name: "currentPassword", value: "" } });
            handleInput({ target: { name: "password", value: "" } });
            handleInput({ target: { name: "cnfPassword", value: "" } });
            setSuccessData({ title: t("success.changesSaved") });
          },
          onError: (error) => {
            // biome-ignore lint/suspicious/noExplicitAny: legacy
            const detail = (error as any)?.response?.data?.detail;
            setPasswordFormError(detail ?? t("errors.saveChanges"));
            setErrorData({
              title: t("errors.saveChanges"),
              list: [detail],
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
            const newUserData = cloneDeep(userData);
            newUserData!.profile_image = profile_picture;
            setUserData(newUserData);
            setSuccessData({ title: t("success.changesSaved") });
          },
          onError: (error) => {
            setErrorData({
              title: t("errors.saveChanges"),
              // biome-ignore lint/suspicious/noExplicitAny: legacy
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
      setSuccessData({ title: t("auth.saveApiKeySuccess") });
      setHasApiKey(true);
      setValidApiKey(true);
      setLoadingApiKey(false);
      handleInput({ target: { name: "apikey", value: "" } });
    },
    onError: (error) => {
      setErrorData({
        title: t("errors.saveApiKey"),
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        list: [(error as any)?.response?.data?.detail],
      });
      setHasApiKey(false);
      setValidApiKey(false);
      setLoadingApiKey(false);
    },
  });

  const _handleSaveKey = (apikey: string) => {
    if (apikey) {
      mutate({ key: apikey });
      storeApiKey(apikey);
    }
  };

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    if (["currentPassword", "password", "cnfPassword"].includes(name)) {
      setPasswordFormError(null);
    }
  }

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <GeneralPageHeaderComponent />

      <div className="flex w-full flex-col gap-6">
        <LanguageFormComponent />

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
          <CustomSettingsPasswordFormGate>
            <PasswordFormComponent
              currentPassword={currentPassword}
              password={password}
              cnfPassword={cnfPassword}
              handleInput={handleInput}
              handlePatchPassword={handlePatchPassword}
              serverError={passwordFormError}
            />
          </CustomSettingsPasswordFormGate>
        )}
      </div>

      <CustomTelemetryToggle />

      <CustomRegistrationData />

      <CustomTermsLinks />
    </div>
  );
};

export default GeneralPage;
