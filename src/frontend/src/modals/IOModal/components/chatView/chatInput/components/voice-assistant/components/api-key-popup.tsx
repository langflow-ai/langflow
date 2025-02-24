import IconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "@/components/ui/button";
import { FC, useState } from "react";

interface ApiKeyPopupProps {
  onSubmit: (apiKey: string) => void;
  onClose?: () => void;
  isOpen: boolean;
}

const ApiKeyPopup: FC<ApiKeyPopupProps> = ({ onSubmit, onClose, isOpen }) => {
  const [apiKey, setApiKey] = useState<string>("");

  if (!isOpen) return null;

  const handleSubmit = () => {
    onSubmit(apiKey);
    setApiKey("");
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-[99] flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md overflow-hidden rounded-lg bg-background shadow-lg">
            <div className="p-6">
              <h2 className="mb-2 text-xl font-semibold">
                Enable Voice Transcription
              </h2>
              <p className="mb-6 text-muted-foreground">
                Voice transcription is powered by OpenAI. To enable it, enter
                your API key.
              </p>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="openai-api-key"
                    className="flex items-center font-medium"
                  >
                    OpenAI API key
                    <span className="ml-1 text-red-500">*</span>
                    <button
                      type="button"
                      className="ml-2 text-muted-foreground hover:text-foreground"
                      onClick={() =>
                        window.open(
                          "https://platform.openai.com/api-keys",
                          "_blank",
                        )
                      }
                    >
                      <IconComponent name="QuestionMarkCircle" />
                    </button>
                  </label>
                </div>

                <InputComponent
                  password
                  value={apiKey}
                  onChange={(value) => setApiKey(value)}
                  placeholder="Enter a token..."
                  nodeStyle
                />

                <Button
                  onClick={handleSubmit}
                  disabled={!apiKey.trim()}
                  className="mt-4 w-full bg-black py-6 text-white hover:bg-gray-800"
                >
                  Start Transcribing
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ApiKeyPopup;
