import PageLayout from "../../components/pageLayout";
import { useGlobalVariablesStore } from "../../stores/globalVariables";
import AddNewVariableButton from "./components/addNewVariableButton";

export default function GlobalVariablesPage() {
  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariables
  );
  return (
    <PageLayout
      title="Variables"
      description="set your own personal varaibles and use it on your flow"
    >
      {Object.keys(globalVariables).length > 0 ? (
        <div></div>
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
