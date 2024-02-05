import ShadTooltip from "../../components/ShadTooltipComponent";
import IconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import { deleteGlobalVariable } from "../../controllers/API";
import { useGlobalVariablesStore } from "../../stores/globalVariables";
import AddNewVariableButton from "./components/addNewVariableButton";

//TODO: improve UI

export default function GlobalVariablesPage() {
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries
  );
  const removeGlobalVariable = useGlobalVariablesStore(
    (state) => state.removeGlobalVariable
  );

  function handleDelete(key: string) {
    deleteGlobalVariable(key).then((_) => removeGlobalVariable(key));
  }
  return (
    <PageLayout
      title="Variables"
      description="set your own personal varaibles and use it on your flow"
    >
      {globalVariablesEntries.length > 0 ? (
        <div className="flex h-full w-full flex-col justify-around">
          {globalVariablesEntries.map((key, index) => (
            <div className="flex w-full items-start" key={index}>
              <span>{key}</span>
              <ShadTooltip content="Delete">
                <button onClick={(_) => handleDelete(key)} className="ml-auto">
                  <IconComponent name="Trash2" />
                </button>
              </ShadTooltip>
            </div>
          ))}
          <AddNewVariableButton />
        </div>
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center align-middle">
          <div>
            <p> create your first variable</p>
            <AddNewVariableButton />
          </div>
        </div>
      )}
    </PageLayout>
  );
}
