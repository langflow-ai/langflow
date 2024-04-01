import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import NewFlowCardComponent from "./components/NewFlowCardComponent";
import UndrawCardComponent from "./components/undrawCards";

export default function NewFlowModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const examples = useFlowsManagerStore((state) => state.examples);

  return (
    <BaseModal size="three-cards" open={open} setOpen={setOpen}>
      <BaseModal.Header description={"Select a template below"}>
        <span className="pr-2" data-testid="modal-title">
          Get Started
        </span>
        {/* <IconComponent
            name="Group"
            className="h-6 w-6 stroke-2 text-primary "
            aria-hidden="true"
          /> */}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className=" mb-5 grid h-fit w-full grid-cols-3 gap-4 overflow-auto pb-6 custom-scroll">
          <NewFlowCardComponent />
          {/* {examples.map((example, idx) => {
            return <UndrawCardComponent key={idx} flow={example} />;
          })} */}
          {examples.find((e) => e.name == "Basic Prompting") && (
            <UndrawCardComponent
              key={1}
              flow={examples.find((e) => e.name == "Basic Prompting")!}
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
              key={1}
              flow={examples.find((e) => e.name == "Document QA")!}
            />
          )}
          {examples.find((e) => e.name == "Prompt Chaining") && (
            <UndrawCardComponent
              key={1}
              flow={examples.find((e) => e.name == "Prompt Chaining")!}
            />
          )}
          {examples.find((e) => e.name == "Blog Writer") && (
            <UndrawCardComponent
              key={1}
              flow={examples.find((e) => e.name == "Blog Writer")!}
            />
          )}
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
