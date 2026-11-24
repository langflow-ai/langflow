import type React from "react";
import {
  Trans as TransComponent,
  type TransProps,
  useTranslation,
} from "react-i18next";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";

const Trans = TransComponent as unknown as React.FC<TransProps<string>>;

interface NoInputViewProps {
  isBuilding: boolean;
  sendMessage: (args: { repeat: number }) => Promise<void>;
  stopBuilding: () => void;
}

const NoInputView: React.FC<NoInputViewProps> = ({
  isBuilding,
  sendMessage,
  stopBuilding,
}) => {
  const { t } = useTranslation();
  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <div className="flex w-full flex-col items-center justify-center gap-3 rounded-md border border-input bg-muted p-2 py-4">
        {!isBuilding ? (
          <Button
            data-testid="button-send"
            className="font-semibold"
            onClick={async () => {
              await sendMessage({
                repeat: 1,
              });
            }}
          >
            {t("playground.runFlow")}
          </Button>
        ) : (
          <Button
            onClick={stopBuilding}
            data-testid="button-stop"
            unstyled
            className="form-modal-send-button cursor-pointer bg-muted text-foreground hover:bg-secondary-hover dark:hover:bg-input"
          >
            <div className="flex items-center gap-2 rounded-md text-sm font-medium">
              {t("flowBuild.stop")}
              <Loading className="h-4 w-4" />
            </div>
          </Button>
        )}

        <p className="text-muted-foreground">
          <Trans
            i18nKey="playground.noInputHint"
            components={{
              1: (
                <a
                  className="underline underline-offset-4"
                  target="_blank"
                  href="https://docs.langflow.org/components-io#chat-input"
                  rel="noopener noreferrer"
                />
              ),
            }}
          />
        </p>
      </div>
    </div>
  );
};

export default NoInputView;
