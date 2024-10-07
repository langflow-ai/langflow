import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useEffect } from "react";
import DeleteConfirmationModal from "../../modals/deleteConfirmationModal";
import useAlertStore from "../../stores/alertStore";
import { InputGlobalComponentType } from "../../types/components";
import { cn } from "../../utils/utils";
import GlobalVariableModal from "../GlobalVariableModal/GlobalVariableModal";
import ForwardedIconComponent from "../genericIconComponent";
import InputComponent from "../inputComponent";
import { CommandItem } from "../ui/command";

export default function InputGlobalComponent({
  disabled,
  onChange,
  name,
  data,
  editNode = false,
}: InputGlobalComponentType): JSX.Element {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();

  useEffect(() => {
    if (data && globalVariables)
      if (
        data.load_from_db &&
        !globalVariables.find((variable) => variable.name === data.value)
      ) {
        onChange("", false, true);
      }
  }, [globalVariables]);

  async function handleDelete(key: string) {
    if (!globalVariables) return;
    const id = globalVariables.find((variable) => variable.name === key)?.id;
    if (id !== undefined) {
      mutateDeleteGlobalVariable(
        { id },
        {
          onSuccess: () => {
            if (data?.value === key && data?.load_from_db) {
              onChange("", false);
            }
          },
          onError: () => {
            setErrorData({
              title: "Error deleting variable",
              list: [cn("ID not found for variable: ", key)],
            });
          },
        },
      );
    } else {
      setErrorData({
        title: "Error deleting variable",
        list: [cn("ID not found for variable: ", key)],
      });
    }
  }
  return (
    <InputComponent
      id={"input-" + name}
      editNode={editNode}
      disabled={disabled}
      password={data.password ?? false}
      value={data.value ?? ""}
      options={globalVariables?.map((variable) => variable.name) ?? []}
      optionsPlaceholder={"Global Variables"}
      optionsIcon="Globe"
      optionsButton={
        <GlobalVariableModal>
          <CommandItem value="doNotFilter-addNewVariable">
            <ForwardedIconComponent
              name="Plus"
              className={cn("mr-2 h-4 w-4 text-primary")}
              aria-hidden="true"
            />
            <span>Add New Variable</span>
          </CommandItem>
        </GlobalVariableModal>
      }
      optionButton={(option) => (
        <DeleteConfirmationModal
          onConfirm={(e) => {
            e.stopPropagation();
            e.preventDefault();
            handleDelete(option);
          }}
          description={'variable "' + option + '"'}
          asChild
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
            }}
            className="pr-1"
          >
            <ForwardedIconComponent
              name="Trash2"
              className={cn(
                "h-4 w-4 text-primary opacity-0 hover:text-status-red group-hover:opacity-100",
              )}
              aria-hidden="true"
            />
          </button>
        </DeleteConfirmationModal>
      )}
      selectedOption={
        data?.load_from_db &&
        globalVariables &&
        globalVariables
          ?.map((variable) => variable.name)
          .includes(data?.value ?? "")
          ? data?.value
          : ""
      }
      setSelectedOption={(value) => {
        onChange(value, value !== "" ? true : false);
      }}
      onChange={(value, skipSnapshot) => {
        onChange(value, false, skipSnapshot);
      }}
    />
  );
}
