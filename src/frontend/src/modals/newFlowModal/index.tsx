import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import NewFlowCardComponent from "./components/NewFlowCardComponent";
import UndrawCardComponent from "./components/undrawCards";
import { useTranslation } from "react-i18next";

export default function NewFlowModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const examples = useFlowsManagerStore((state) => state.examples);
  const { t } = useTranslation();

  examples?.forEach((example) => {
    if (example.name === "Blog Writter") {
      example.name = "Blog Writer";
    }
  });

  return (
    <BaseModal size="three-cards" open={open} setOpen={setOpen}>
      <BaseModal.Header description={t("Select a template below")}>
        <span className="pr-2" data-testid="modal-title">
          {t("Get Started")}
        </span>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="mb-5 grid h-fit w-full grid-cols-3 gap-4 overflow-auto pb-6 custom-scroll">
          <NewFlowCardComponent />

          {examples.find((e) => e.name == "Basic Prompting (Hello, World)") && (
            <UndrawCardComponent
              key={0}
              flow={
                examples.find(
                  (e) => e.name == "Basic Prompting (Hello, World)",
                )!
              }
            />
          )}
          {examples.find((e) => e.name == "Memory Chatbot") && (
            <UndrawCardComponent
              key={1}
              flow={examples.find((e) => e.name == "Memory Chatbot")!}
            />
          )}
          {examples.find((e) => e.name == "Document QA") && (
            <UndrawCardComponent
              key={2}
              flow={examples.find((e) => e.name == "Document QA")!}
            />
          )}
          {examples.find((e) => e.name == "Blog Writer") && (
            <UndrawCardComponent
              key={3}
              flow={examples.find((e) => e.name == "Blog Writer")!}
            />
          )}
          {examples.find((e) => e.name == "Vector Store RAG") && (
            <UndrawCardComponent
              key={4}
              flow={examples.find((e) => e.name == "Vector Store RAG")!}
            />
          )}
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
