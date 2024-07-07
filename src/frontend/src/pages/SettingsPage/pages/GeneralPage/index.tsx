import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import { useGetProfilePicturesQuery } from "@/controllers/API/queries/files";
import { useContext, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CONTROL_PATCH_USER_STATE } from "../../../../constants/constants";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../stores/storeStore";
import {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../../../types/components";
import usePatchPassword from "../hooks/use-patch-password";
import usePatchProfilePicture from "../hooks/use-patch-profile-picture";
import useScrollToElement from "../hooks/use-scroll-to-element";
import GeneralPageHeaderComponent from "./components/GeneralPageHeader";
import PasswordFormComponent from "./components/PasswordForm";
import ProfilePictureFormComponent from "./components/ProfilePictureForm";
import useGetProfilePictures from "./components/ProfilePictureForm/components/profilePictureChooserComponent/hooks/use-get-profile-pictures";
import StoreApiKeyFormComponent from "./components/StoreApiKeyForm";

export const GeneralPage = () => {
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId,
  );

  const { scrollId } = useParams();

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE,
  );

  const { autoLogin } = useContext(AuthContext);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const hasStore = useStoreStore((state) => state.hasStore);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const loadingApiKey = useStoreStore((state) => state.loadingApiKey);
  const { password, cnfPassword, profilePicture, apikey } = inputState;

  const { storeApiKey } = useContext(AuthContext);
  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const { handlePatchPassword } = usePatchPassword(
    userData,
    setSuccessData,
    setErrorData,
  );

  const handleGetProfilePictures = () => {
    const { data } = useGetProfilePicturesQuery({});
    return data;
  };

  const { handlePatchProfilePicture } = usePatchProfilePicture(
    setSuccessData,
    setErrorData,
    userData,
    setUserData,
  );

  useScrollToElement(scrollId, setCurrentFlowId);

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

  const handleSaveKey = (apikey: string) => {
    if (apikey) {
      mutate({ key: apikey });
      storeApiKey(apikey);
    }
  };

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <GeneralPageHeaderComponent />

      <div className="grid gap-6">
        <ProfilePictureFormComponent
          profilePicture={profilePicture}
          handleInput={handleInput}
          handlePatchProfilePicture={handlePatchProfilePicture}
          handleGetProfilePictures={handleGetProfilePictures}
          userData={userData}
        />

        {!autoLogin && (
          <PasswordFormComponent
            password={password}
            cnfPassword={cnfPassword}
            handleInput={handleInput}
            handlePatchPassword={handlePatchPassword}
          />
        )}
        {hasStore && (
          <StoreApiKeyFormComponent
            apikey={apikey}
            handleInput={handleInput}
            handleSaveKey={handleSaveKey}
            loadingApiKey={loadingApiKey}
            validApiKey={validApiKey}
            hasApiKey={hasApiKey}
          />
        )}
      </div>
    </div>
  );
};

export default GeneralPage;
