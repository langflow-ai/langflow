import { getModalPropsApiKey } from "@/pages/SettingsPage/pages/ApiKeysPage/helpers/get-modal-props";

export const SecretKeyModalButton = ({
  userId,
}: {
  userId: string;
}): JSX.Element => {
  const modalProps = getModalPropsApiKey();

  return <></>;
};

export default SecretKeyModalButton;
