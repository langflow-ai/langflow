import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useEffect } from "react";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";
import useAlertStore from "../../../../stores/alertStore";
import { cn } from "../../../../utils/utils";
import GlobalVariableModal from "../../../GlobalVariableModal/GlobalVariableModal";
import ForwardedIconComponent from "../../../genericIconComponent";
import InputComponent from "../../../inputComponent";
import { CommandItem } from "../../../ui/command";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import { InputGlobalComponentType, InputProps } from "../../types";

export default function InputGlobalComponent({
  disabled,
  handleOnNewValue,
  value,
  id,
  load_from_db,
  password,
  editNode = false,
}: InputProps<string, InputGlobalComponentType>): JSX.Element {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();

  useEffect(() => {
    if (globalVariables)
      if (
        load_from_db &&
        !globalVariables.find((variable) => variable.name === value)
      ) {
        handleOnNewValue(
          { value: "", load_from_db: false },
          { skipSnapshot: true },
        );
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
            if (value === key && load_from_db) {
              handleOnNewValue({ value: "", load_from_db: false });
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
      nodeStyle
      placeholder={getPlaceholder(disabled, "Type something...")}
      id={id}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={value ?? ""}
      options={globalVariables?.map((variable) => variable.name) ?? []}
      optionsPlaceholder={"Global Variables"}
      optionsIcon="Globe"
      optionsButton={
        <GlobalVariableModal disabled={disabled}>
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
        load_from_db &&
        globalVariables &&
        globalVariables?.map((variable) => variable.name).includes(value ?? "")
          ? value
          : ""
      }
      setSelectedOption={(value) => {
        handleOnNewValue({
          value: value,
          load_from_db: value !== "" ? true : false,
        });
      }}
      onChange={(value, skipSnapshot) => {
        handleOnNewValue(
          { value: value, load_from_db: false },
          { skipSnapshot },
        );
      }}
    />
  );
}
