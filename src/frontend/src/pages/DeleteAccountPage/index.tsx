import { useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import BaseModal from "../../modals/baseModal";

export default function DeleteAccountPage() {
  const { t } = useTranslation();
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleDeleteAccount = () => {
    // Implement your account deletion logic here
    // For example, make an API call to delete the account
    // Upon successful deletion, you can redirect the user to another page
    // Implement the logic to redirect the user after account deletion.
    // For example, use react-router-dom's useHistory hook.
  };

  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <LangflowLogo
          title={t("deleteAccount.logoTitle")}
          className="mb-4 h-10 w-10 scale-[1.5]"
        />
        <span className="mb-4 text-center text-2xl font-semibold text-primary">
          {t("deleteAccount.heading")}
        </span>
        <Input
          className="bg-background"
          placeholder={t("auth.confirmPassword")}
        />

        <BaseModal
          open={showConfirmation}
          setOpen={setShowConfirmation}
          size="x-small"
        >
          <BaseModal.Header
            description={t("deleteAccount.irreversibleDescription")}
          >
            <h3>{t("deleteAccount.areYouSure")}</h3>
          </BaseModal.Header>
          <BaseModal.Trigger>
            <Button
              variant="default"
              className="w-full hover:bg-status-red"
              onClick={() => setShowConfirmation(true)}
            >
              {t("deleteAccount.deleteButton")}
            </Button>
          </BaseModal.Trigger>
          <BaseModal.Content>
            <div className="flex h-full w-full flex-col justify-end">
              <Button
                variant="default"
                className="w-full hover:bg-status-red"
                onClick={() => handleDeleteAccount()}
              >
                {t("deleteAccount.deleteButton")}
              </Button>
            </div>
          </BaseModal.Content>
        </BaseModal>
      </div>
    </div>
  );
}
