import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useGetTotpStatus,
  usePostTotpDisable,
  usePostTotpEnable,
  usePostTotpSetup,
} from "@/controllers/API/queries/auth";
import { Button } from "../../../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";
import { Input } from "../../../../../../components/ui/input";
import useAlertStore from "../../../../../../stores/alertStore";

type TotpFormView = "status" | "setup" | "disable";

const TotpFormComponent = () => {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [view, setView] = useState<TotpFormView>("status");
  const [setupData, setSetupData] = useState<{
    provisioning_uri: string;
    raw_secret: string;
  } | null>(null);
  const [code, setCode] = useState("");

  const { data: statusData, refetch: refetchStatus } = useGetTotpStatus();
  const totpEnabled = statusData?.totp_enabled ?? false;

  const { mutate: mutateSetup, isPending: isSetupPending } = usePostTotpSetup();
  const { mutate: mutateEnable, isPending: isEnablePending } =
    usePostTotpEnable();
  const { mutate: mutateDisable, isPending: isDisablePending } =
    usePostTotpDisable();

  const handleStartEnable = () => {
    mutateSetup(undefined, {
      onSuccess: (data) => {
        setSetupData(data);
        setCode("");
        setView("setup");
      },
      onError: (error) => {
        setErrorData({
          title: t("errors.saveChanges"),
          list: [
            (error as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail,
          ],
        });
      },
    });
  };

  const handleVerifyAndEnable = () => {
    if (!setupData) return;
    mutateEnable(
      { code: code.trim(), raw_secret: setupData.raw_secret },
      {
        onSuccess: () => {
          setSuccessData({ title: t("success.changesSaved") });
          setView("status");
          setCode("");
          setSetupData(null);
          refetchStatus();
        },
        onError: (error) => {
          setErrorData({
            title: t("settings.totpInvalidCode"),
            list: [
              (error as { response?: { data?: { detail?: string } } })?.response
                ?.data?.detail,
            ],
          });
        },
      },
    );
  };

  const handleStartDisable = () => {
    setCode("");
    setView("disable");
  };

  const handleConfirmDisable = () => {
    mutateDisable(
      { code: code.trim() },
      {
        onSuccess: () => {
          setSuccessData({ title: t("success.changesSaved") });
          setView("status");
          setCode("");
          refetchStatus();
        },
        onError: (error) => {
          setErrorData({
            title: t("settings.totpInvalidCode"),
            list: [
              (error as { response?: { data?: { detail?: string } } })?.response
                ?.data?.detail,
            ],
          });
        },
      },
    );
  };

  const handleCancel = () => {
    setView("status");
    setCode("");
    setSetupData(null);
  };

  if (view === "setup" && setupData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.totpSetupTitle")}</CardTitle>
          <CardDescription>
            {t("settings.totpSetupDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex">
            <div className="rounded-lg border bg-white p-3">
              <QRCodeSVG
                value={setupData.provisioning_uri}
                size={180}
                level="M"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {t("settings.totpManualSecret")}{" "}
            <span className="font-mono font-semibold tracking-wider">
              {setupData.raw_secret}
            </span>
          </p>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium">
              {t("settings.totpCodeLabel")}
            </label>
            <Input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder={t("settings.totpCodePlaceholder")}
              className="w-40 text-center font-mono text-lg tracking-widest"
              placeholderClassName="left-0 w-40 justify-center pl-0 text-center font-mono text-lg tracking-widest text-muted-foreground/40"
              autoComplete="one-time-code"
            />
          </div>
        </CardContent>
        <CardFooter className="flex gap-2 border-t px-6 py-4">
          <Button
            type="button"
            onClick={handleVerifyAndEnable}
            disabled={code.length < 6 || isEnablePending}
          >
            {t("settings.totpVerifyButton")}
          </Button>
          <Button type="button" variant="outline" onClick={handleCancel}>
            {t("settings.totpCancelButton")}
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (view === "disable") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.totpTitle")}</CardTitle>
          <CardDescription>
            {t("settings.totpDisableConfirmDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium">
              {t("settings.totpCodeLabel")}
            </label>
            <Input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder={t("settings.totpCodePlaceholder")}
              className="w-40 text-center font-mono text-lg tracking-widest"
              placeholderClassName="left-0 w-40 justify-center pl-0 text-center font-mono text-lg tracking-widest text-muted-foreground/40"
              autoComplete="one-time-code"
            />
          </div>
        </CardContent>
        <CardFooter className="flex gap-2 border-t px-6 py-4">
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirmDisable}
            disabled={code.length < 6 || isDisablePending}
          >
            {t("settings.totpConfirmDisableButton")}
          </Button>
          <Button type="button" variant="outline" onClick={handleCancel}>
            {t("settings.totpCancelButton")}
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.totpTitle")}</CardTitle>
        <CardDescription>{t("settings.totpDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          {totpEnabled ? t("settings.totpEnabled") : t("settings.totpDisabled")}
        </p>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        {totpEnabled ? (
          <Button
            type="button"
            variant="destructive"
            onClick={handleStartDisable}
          >
            {t("settings.totpDisableButton")}
          </Button>
        ) : (
          <Button
            type="button"
            onClick={handleStartEnable}
            disabled={isSetupPending}
          >
            {t("settings.totpEnableButton")}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};

export default TotpFormComponent;
