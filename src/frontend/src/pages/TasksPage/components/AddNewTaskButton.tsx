import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useGetActors } from "@/controllers/API/queries/actors";
import { usePostTask } from "@/controllers/API/queries/tasks/use-post-task";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { Task } from "@/types/Task";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

// Form validation schema
const taskSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().min(1, "Description is required"),
  attachments: z.array(z.string()),
  author_id: z.string().uuid("Invalid author ID"),
  assignee_id: z.string().uuid("Invalid assignee ID"),
  category: z.string().min(1, "Category is required"),
  state: z.string().min(1, "State is required"),
  status: z.enum(["pending", "processing", "completed", "failed"]),
});

type TaskFormValues = z.infer<typeof taskSchema>;

type AddNewTaskButtonProps = {
  children: JSX.Element;
  asChild?: boolean;
  initialData?: Task;
  mode?: "create" | "edit";
  onUpdate?: (data: Task) => void;
  openFromParent?: boolean;
  setOpenFromParent?: (open: boolean) => void;
};

export default function AddNewTaskButton({
  children,
  asChild,
  initialData,
  mode = "create",
  onUpdate,
  openFromParent,
  setOpenFromParent,
}: AddNewTaskButtonProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [attachmentInput, setAttachmentInput] = useState("");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: mutateAddTask, isPending: isAddPending } = usePostTask();
  const [isEditPending, setIsEditPending] = useState(false);
  const queryClient = useQueryClient();

  // Control open state from parent if provided
  useEffect(() => {
    if (openFromParent !== undefined) {
      setOpen(openFromParent);
    }
  }, [openFromParent]);

  const handleSetOpen = (value: boolean) => {
    setOpen(value);
    if (setOpenFromParent) {
      setOpenFromParent(value);
    }
  };

  // Fetch actors for the current project
  const { data: actors, isLoading: actorsLoading } = useGetActors();

  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      title: initialData?.title || "",
      description: initialData?.description || "",
      attachments: initialData?.attachments || [],
      author_id: initialData?.author_id || "",
      assignee_id: initialData?.assignee_id || "",
      category: initialData?.category || "",
      state: initialData?.state || "",
      status: (initialData?.status as any) || "pending",
    },
  });

  // Update form values when initialData changes (for edit mode)
  useEffect(() => {
    if (initialData && mode === "edit") {
      form.reset({
        title: initialData.title,
        description: initialData.description,
        attachments: initialData.attachments,
        author_id: initialData.author_id,
        assignee_id: initialData.assignee_id,
        category: initialData.category,
        state: initialData.state,
        status: initialData.status,
      });
    }
  }, [initialData, form, mode]);

  function handleAddAttachment(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && attachmentInput.trim()) {
      e.preventDefault();
      const currentAttachments = form.getValues("attachments");
      form.setValue("attachments", [
        ...currentAttachments,
        attachmentInput.trim(),
      ]);
      setAttachmentInput("");
    }
  }

  function handleRemoveAttachment(index: number) {
    const currentAttachments = form.getValues("attachments");
    form.setValue(
      "attachments",
      currentAttachments.filter((_, i) => i !== index),
    );
  }

  async function handleEditTask(data: TaskFormValues) {
    if (!initialData) return;

    setIsEditPending(true);
    try {
      const response = await api.put(
        `${getURL("TASKS")}/${initialData.id}`,
        data,
      );
      setSuccessData({
        title: `Task "${data.title}" updated successfully`,
      });
      handleSetOpen(false);
      form.reset();

      // Invalidate query to refresh data
      queryClient.invalidateQueries({ queryKey: ["tasks"] });

      // Call onUpdate callback if provided
      if (onUpdate) {
        onUpdate(response.data);
      }
    } catch (error: any) {
      setErrorData({
        title: "Error updating task",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred while updating the task. Please try again.",
        ],
      });
    } finally {
      setIsEditPending(false);
    }
  }

  function onSubmit(data: TaskFormValues) {
    if (mode === "edit") {
      handleEditTask(data);
      return;
    }

    mutateAddTask(data, {
      onSuccess: (res) => {
        setSuccessData({
          title: `Task "${res.title}" created successfully`,
        });
        handleSetOpen(false);
        form.reset();
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

  const isSubmitting = mode === "create" ? isAddPending : isEditPending;
  const modalTitle = mode === "create" ? "Create Task" : "Edit Task";
  const modalDescription =
    mode === "create"
      ? "Create a new task to manage your workflow"
      : "Update task details";
  const submitButtonText = mode === "create" ? "Create Task" : "Update Task";

  return (
    <BaseModal open={open} setOpen={handleSetOpen} size="three-cards">
      <BaseModal.Header description={modalDescription}>
        <span className="pr-2">{modalTitle}</span>
        <ForwardedIconComponent
          name="SquareCheckBig"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      {/* Only show trigger when in create mode, not in edit mode */}
      {mode === "create" && (
        <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      )}
      <BaseModal.Content className="max-h-[80vh] overflow-y-auto">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-4">
              <div className="rounded-lg border p-4">
                <h3 className="mb-4 text-sm font-medium">Task Details</h3>
                <div className="space-y-4">
                  <FormField
                    control={form.control}
                    name="title"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Title</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter task title..." {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Enter task description..."
                            className="h-24 resize-none"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="attachments"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Attachments</FormLabel>
                        <FormControl>
                          <div className="space-y-2">
                            <Input
                              value={attachmentInput}
                              onChange={(e) =>
                                setAttachmentInput(e.target.value)
                              }
                              onKeyDown={handleAddAttachment}
                              placeholder="Type and press Enter to add attachments..."
                            />
                            <div className="flex flex-wrap gap-2">
                              {field.value.map((attachment, index) => (
                                <Badge
                                  key={index}
                                  variant="secondary"
                                  className="flex items-center gap-1"
                                >
                                  {attachment}
                                  <button
                                    type="button"
                                    onClick={() =>
                                      handleRemoveAttachment(index)
                                    }
                                    className="ml-1 rounded-full p-1 hover:bg-background/80"
                                  >
                                    <ForwardedIconComponent
                                      name="X"
                                      className="h-3 w-3"
                                    />
                                  </button>
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <div className="rounded-lg border p-4">
                <h3 className="mb-4 text-sm font-medium">
                  Assignment & Status
                </h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="author_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Author</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select author" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {actorsLoading ? (
                              <SelectItem value="loading" disabled>
                                Loading actors...
                              </SelectItem>
                            ) : actors && actors.length > 0 ? (
                              actors.map((actor) => (
                                <SelectItem key={actor.id} value={actor.id}>
                                  <div className="flex items-center gap-2">
                                    <ForwardedIconComponent
                                      name={
                                        actor.entity_type === "user"
                                          ? "User"
                                          : "Workflow"
                                      }
                                      className="h-4 w-4 text-muted-foreground"
                                    />
                                    {actor.name ||
                                      (actor.entity_type === "user"
                                        ? "User"
                                        : "Flow")}
                                  </div>
                                </SelectItem>
                              ))
                            ) : (
                              <SelectItem value="none" disabled>
                                No actors available
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="assignee_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Assignee</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select assignee" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {actorsLoading ? (
                              <SelectItem value="loading" disabled>
                                Loading actors...
                              </SelectItem>
                            ) : actors && actors.length > 0 ? (
                              actors.map((actor) => (
                                <SelectItem key={actor.id} value={actor.id}>
                                  <div className="flex items-center gap-2">
                                    <ForwardedIconComponent
                                      name={
                                        actor.entity_type === "user"
                                          ? "User"
                                          : "Workflow"
                                      }
                                      className="h-4 w-4 text-muted-foreground"
                                    />
                                    {actor.name ||
                                      (actor.entity_type === "user"
                                        ? "User"
                                        : "Flow")}
                                  </div>
                                </SelectItem>
                              ))
                            ) : (
                              <SelectItem value="none" disabled>
                                No actors available
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="category"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Category</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter category..." {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="state"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>State</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter state..." {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="status"
                    render={({ field }) => (
                      <FormItem className="col-span-2">
                        <FormLabel>Status</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select status" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="pending">Pending</SelectItem>
                            <SelectItem value="processing">
                              Processing
                            </SelectItem>
                            <SelectItem value="completed">Completed</SelectItem>
                            <SelectItem value="failed">Failed</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            </div>
          </form>
        </Form>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: submitButtonText,
          dataTestId: mode === "create" ? "save-task-btn" : "update-task-btn",
          onClick: form.handleSubmit(onSubmit),
          loading: isSubmitting,
        }}
      />
    </BaseModal>
  );
}
