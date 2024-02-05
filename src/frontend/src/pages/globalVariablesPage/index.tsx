import PageLayout from "../../components/pageLayout";
import { useGlobalVariablesStore } from "../../stores/globalVariables";
import AddNewVariableButton from "./components/addNewVariableButton";

export default function GlobalVariablesPage() {
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries
  );
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
