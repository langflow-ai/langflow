import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DialogOperation, useDialogSubmit } from "@/hooks/useDialogSubmit";
import RenderInputParameters from "../RenderInputParameters";

export const NodeDialog = ({ open, onClose, dialogInputs }) => {
  const { submitDialogData, loading } = useDialogSubmit();

  const mockDialogInputs = {
    functionality: "create", // create, update, delete
    fields: {
      data: {
        id: "AstraDB-vdMMh",
        node: {
          beta: false,
          conditional_paths: [],
          custom_fields: {},
          edited: false,
          field_order: ["new_database_name", "cloud_provider", "region"],
          frozen: false,
          legacy: false,
          metadata: {},
          minimized: false,
          output_types: [],
          outputs: [],
          pinned: false,
          description: "Ingest and search documents in Astra DB",
          display_name: "Astra DB",
          documentation: "Documentation for Astra DB component",
          template: {
            // these are the fields that are rendered in the dialog
            cloud_provider: {
              _input_type: "DropdownInput",
              advanced: false,
              combobox: false,
              dialog_inputs: [],
              display_name: "Cloud Provider",
              dynamic: false,
              info: "Cloud provider for the new database.",
              name: "cloud_provider",
              options: [
                "Amazon Web Services",
                "Google Cloud Platform",
                "Microsoft Azure",
              ],
              options_metadata: [],
              placeholder: "",
              required: true,
              show: true,
              title_case: false,
              tool_mode: false,
              trace_as_metadata: true,
              type: "str",
              value: "",
              list: false,
              readonly: false,
            },
            new_database_name: {
              _input_type: "StrInput",
              advanced: false,
              display_name: "New Database Name",
              dynamic: false,
              info: "Name of the new database to create in Astra DB.",
              list: false,
              list_add_label: "Add More",
              load_from_db: false,
              name: "new_database_name",
              placeholder: "",
              required: true,
              show: true,
              title_case: false,
              tool_mode: false,
              trace_as_metadata: true,
              type: "str",
              value: "",
              readonly: false,
            },
            region: {
              _input_type: "DropdownInput",
              advanced: false,
              combobox: false,
              dialog_inputs: [],
              display_name: "Region",
              dynamic: false,
              info: "Region for the new database.",
              name: "region",
              options: ["us-east-2", "ap-south-1", "eu-west-1"],
              options_metadata: [],
              placeholder: "",
              required: true,
              show: true,
              title_case: false,
              tool_mode: false,
              trace_as_metadata: true,
              type: "str",
              value: "",
              list: false,
              readonly: false,
            },
          },
        },
        showNode: true,
        type: "AstraDB",
      },
      isToolMode: false,
      showHiddenOutputs: false,
      showNode: true,
      shownOutputs: [],
      types: {
        // TODO: Add types
      },
    },
  };

  const handleSave = async () => {
    try {
      await submitDialogData(
        mockDialogInputs.fields,
        mockDialogInputs?.functionality as DialogOperation,
      );
      onClose();
    } catch (err) {
      console.error("Failed to save dialog data:", err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[700px] gap-2 px-1 py-6">
        <DialogHeader className="px-5 pb-3">
          <DialogTitle>
            <div className="flex items-center">
              <span className="pb-2">
                {mockDialogInputs.fields?.data?.node?.display_name}
              </span>
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="flex items-center gap-2">
              {mockDialogInputs.fields?.data?.node?.description}
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-y-auto">
          <RenderInputParameters {...mockDialogInputs.fields} />
        </div>

        <DialogFooter className="px-5 pt-3">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? "Saving..." : mockDialogInputs.functionality}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
