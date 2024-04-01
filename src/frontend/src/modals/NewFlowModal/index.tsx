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
        <div className=" grid h-full w-full grid-cols-3 gap-3 overflow-auto p-4 custom-scroll">
          <NewFlowCardComponent />
          {/* {examples.map((example, idx) => {
            return <UndrawCardComponent key={idx} flow={example} />;
          })} */}
          {examples[4] && <UndrawCardComponent key={1} flow={examples[4]}/>}
          {examples[2] && <UndrawCardComponent key={2} flow={examples[2]}/>}
          {examples[3] && <UndrawCardComponent key={3} flow={examples[3]}/>}
          {examples[0] && <UndrawCardComponent key={5} flow={examples[0]}/>}
          {examples[1] && <UndrawCardComponent key={4} flow={examples[1]}/>}


        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
