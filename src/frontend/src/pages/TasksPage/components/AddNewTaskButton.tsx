import IconComponent from "@/components/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { usePostTask } from "@/controllers/API/queries/tasks";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { Task } from "@/types/Task";
import { useState } from "react";

export default function AddNewTaskButton({
  children,
  asChild,
}: {
  children: JSX.Element;
  asChild?: boolean;
}): JSX.Element {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [authorId, setAuthorId] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [category, setCategory] = useState("");
  const [state, setState] = useState("");
  const [status, setStatus] = useState("pending");
  const [open, setOpen] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: mutateAddTask } = usePostTask();

  function handleSaveTask() {
    const newTask: Partial<Task> = {
      title,
      description,
      attachments,
      author_id: authorId,
      assignee_id: assigneeId,
      category,
      state,
      status,
    };

    mutateAddTask(newTask, {
      onSuccess: (res) => {
        setTitle("");
        setDescription("");
        setAttachments([]);
        setAuthorId("");
        setAssigneeId("");
        setCategory("");
        setState("");
        setStatus("pending");
        setOpen(false);

        setSuccessData({
          title: `Task "${res.title}" created successfully`,
        });
      },
      onError: (error: any) => {
        setErrorData({
          title: "Error creating task",
          list: [
            error?.response?.data?.detail ||
              "An unexpected error occurred while adding a new task. Please try again.",
          ],
        });
      },
    });
  }

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="medium"
      onSubmit={handleSaveTask}
    >
      <BaseModal.Header description="Create a new task to manage your workflow.">
        <span className="pr-2">Create Task</span>
        <IconComponent
          name="SquareCheckBig"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Label>Title</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter task title..."
            />
          </div>
          <div className="col-span-2">
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter task description..."
              className="h-24 resize-none"
            />
          </div>
          <div className="col-span-2">
            <Label>Attachments</Label>
            <Input
              value={attachments.join(", ")}
              onChange={(e) => setAttachments(e.target.value.split(", "))}
              placeholder="Enter attachments (comma-separated)..."
            />
          </div>
          <div>
            <Label>Author ID</Label>
            <Input
              value={authorId}
              onChange={(e) => setAuthorId(e.target.value)}
              placeholder="Enter author ID..."
            />
          </div>
          <div>
            <Label>Assignee ID</Label>
            <Input
              value={assigneeId}
              onChange={(e) => setAssigneeId(e.target.value)}
              placeholder="Enter assignee ID..."
            />
          </div>
          <div>
            <Label>Category</Label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Enter category..."
            />
          </div>
          <div>
            <Label>State</Label>
            <Input
              value={state}
              onChange={(e) => setState(e.target.value)}
              placeholder="Enter state..."
            />
          </div>
          <div className="col-span-2">
            <Label>Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{ label: "Save Task", dataTestId: "save-task-btn" }}
      />
    </BaseModal>
  );
}
