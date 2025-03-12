import ForwardedIconComponent from "@/components/common/genericIconComponent";
import LoadingComponent from "@/components/common/loadingComponent";
import PageLayout from "@/components/common/pageLayout";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useDeleteSubscription } from "@/controllers/API/queries/subscriptions/use-delete-subscription";
import { useGetSubscriptions } from "@/controllers/API/queries/subscriptions/use-get-subscriptions";
import { useDeleteTask } from "@/controllers/API/queries/tasks/use-delete-task";
import { useGetTasks } from "@/controllers/API/queries/tasks/use-get-tasks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { Subscription } from "@/types/Subscription";
import { Task } from "@/types/Task";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { CellEditRequestEvent, ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import AddNewTaskButton from "./components/AddNewTaskButton";

const POLLING_INTERVAL = 5000; // 5 seconds

export default function TaskPage() {
  const [inputValue, setInputValue] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [taskData, setTaskData] = useState<Task[]>([]);
  const [subscriptionData, setSubscriptionData] = useState<Subscription[]>([]);
  const [showSubscriptions, setShowSubscriptions] = useState(false);
  const [selectedResult, setSelectedResult] = useState<any>(null);
  const [isResultDialogOpen, setIsResultDialogOpen] = useState(false);
  const [resultCopyFeedback, setResultCopyFeedback] = useState(false);
  const [selectedText, setSelectedText] = useState<{
    value: string;
    title: string;
  }>({ value: "", title: "" });
  const [isTextDialogOpen, setIsTextDialogOpen] = useState(false);
  const [textCopyFeedback, setTextCopyFeedback] = useState(false);
  const [selectedTaskToEdit, setSelectedTaskToEdit] = useState<Task | null>(
    null,
  );
  const [isEditTaskDialogOpen, setIsEditTaskDialogOpen] = useState(false);
  const [editFormData, setEditFormData] = useState<Partial<Task>>({});
  const [isBatchEditDialogOpen, setIsBatchEditDialogOpen] = useState(false);
  const [batchEditFormData, setBatchEditFormData] = useState<Partial<Task>>({});
  const [batchEditFields, setBatchEditFields] = useState<
    Record<string, boolean>
  >({
    title: false,
    description: false,
    category: false,
    state: false,
    status: false,
  });
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();
  const queryClient = useQueryClient();

  const {
    data: tasks,
    isLoading: isLoadingTasks,
    error: tasksError,
    refetch: refetchTasks,
  } = useGetTasks({
    refetchInterval: showSubscriptions ? undefined : POLLING_INTERVAL,
  });

  const {
    data: subscriptions,
    isLoading: isLoadingSubscriptions,
    error: subscriptionsError,
    refetch: refetchSubscriptions,
  } = useGetSubscriptions({
    refetchInterval: showSubscriptions ? POLLING_INTERVAL : undefined,
  });

  const { mutate: mutateDeleteTask } = useDeleteTask();
  const { mutate: mutateDeleteSubscription } = useDeleteSubscription();

  useEffect(() => {
    if (tasks && Array.isArray(tasks) && !showSubscriptions) {
      // Sort tasks by created_at in descending order (newest first)
      const sortedTasks = [...tasks].sort((a, b) => {
        return (
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
      });
      setTaskData(sortedTasks);
    }
  }, [tasks, showSubscriptions]);

  useEffect(() => {
    if (subscriptions && Array.isArray(subscriptions) && showSubscriptions) {
      // Sort subscriptions by created_at in descending order (newest first)
      const sortedSubscriptions = [...subscriptions].sort((a, b) => {
        return (
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
      });
      setSubscriptionData(sortedSubscriptions);
    }
  }, [subscriptions, showSubscriptions]);

  const BadgeRenderer = (props: { value: string }) => {
    if (!props.value) return null;

    // If it's a long string, truncate it for display in the badge
    const displayValue =
      typeof props.value === "string" && props.value.length > 20
        ? props.value.substring(0, 20) + "..."
        : props.value;

    return (
      <Badge variant="outline" size="sm">
        {displayValue}
      </Badge>
    );
  };

  const TextRenderer = (props: { value: string; fieldName: string }) => {
    if (!props.value) return null;

    const handleTextClick = () => {
      // Capitalize first letter of field name for the title
      const title =
        props.fieldName.charAt(0).toUpperCase() + props.fieldName.slice(1);
      setSelectedText({ value: props.value, title });
      setIsTextDialogOpen(true);
    };

    // Truncate long text for display in the table
    const maxLength = props.fieldName === "description" ? 100 : 50;
    const displayValue =
      props.value.length > maxLength
        ? props.value.substring(0, maxLength) + "..."
        : props.value;

    return (
      <div
        className="cursor-pointer hover:underline"
        onClick={handleTextClick}
        title={`Click to view full ${props.fieldName}`}
      >
        {displayValue}
      </div>
    );
  };

  const DescriptionRenderer = (props: { value: string }) => {
    return TextRenderer({ value: props.value, fieldName: "description" });
  };

  const DateRenderer = (props: { value: string }) => {
    return props.value ? new Date(props.value).toLocaleString() : "";
  };

  const ResultRenderer = (props: { value: any }) => {
    if (!props.value) return null;

    const handleResultClick = () => {
      setSelectedResult(props.value);
      setIsResultDialogOpen(true);
    };

    // Check if result contains markdown content
    if (hasMarkdownContent(props.value)) {
      return (
        <div
          className="max-w-xs cursor-pointer truncate text-blue-600 hover:underline"
          title="Click to view markdown content"
          onClick={handleResultClick}
        >
          <span className="flex items-center">
            <ForwardedIconComponent name="FileText" className="mr-1 h-4 w-4" />
            Markdown content available
          </span>
        </div>
      );
    }

    // Handle error results
    if (props.value.error) {
      return (
        <div
          className="max-w-xs cursor-pointer truncate text-red-500 hover:underline"
          title="Click to view details"
          onClick={handleResultClick}
        >
          Error: {props.value.error}
        </div>
      );
    }

    // Handle outputs
    if (props.value.outputs && Array.isArray(props.value.outputs)) {
      const outputCount = props.value.outputs.length;
      return (
        <div
          className="max-w-xs cursor-pointer truncate text-green-600 hover:underline"
          title="Click to view results"
          onClick={handleResultClick}
        >
          {outputCount} result{outputCount !== 1 ? "s" : ""} available
        </div>
      );
    }

    // Handle subscription state JSON
    if (typeof props.value === "object" && props.value !== null) {
      // Get a preview of the JSON content
      const jsonPreview = JSON.stringify(props.value).substring(0, 30);

      return (
        <div
          className="max-w-xs cursor-pointer truncate text-purple-600 hover:underline"
          title="Click to view JSON state"
          onClick={handleResultClick}
        >
          <span className="flex items-center">
            <ForwardedIconComponent name="Code" className="mr-1 h-4 w-4" />
            {jsonPreview}
            {jsonPreview.length >= 30 ? "..." : ""}
          </span>
        </div>
      );
    }

    // If it's a simple value, just display it
    if (typeof props.value !== "object") {
      return (
        <span
          className="cursor-pointer hover:underline"
          onClick={handleResultClick}
        >
          {String(props.value)}
        </span>
      );
    }

    // For other objects, display a summarized version
    try {
      // Limit the display to avoid overwhelming the UI
      const summary = JSON.stringify(props.value).substring(0, 50);
      return (
        <div
          className="max-w-xs cursor-pointer truncate hover:underline"
          title="Click to view details"
          onClick={handleResultClick}
        >
          {summary}
          {summary.length >= 50 ? "..." : ""}
        </div>
      );
    } catch (error) {
      return <span>Error displaying result</span>;
    }
  };

  const handleCellEditRequest = async (event: CellEditRequestEvent) => {
    try {
      const { data, colDef, newValue } = event;
      const id = data.id;
      const field = colDef.field as string;

      if (!id || !field) return;

      const updatedData = { ...data, [field]: newValue };

      if (showSubscriptions) {
        // Update subscription
        await api.put(`${getURL("SUBSCRIPTIONS")}/${id}`, {
          [field]: newValue,
        });

        // Update local state
        setSubscriptionData((prevData) =>
          prevData.map((item) =>
            item.id === id ? { ...item, [field]: newValue } : item,
          ),
        );

        // Invalidate query to refresh data
        queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      } else {
        // Update task
        await api.put(`${getURL("TASKS")}/${id}`, {
          [field]: newValue,
        });

        // Update local state
        setTaskData((prevData) =>
          prevData.map((item) =>
            item.id === id ? { ...item, [field]: newValue } : item,
          ),
        );

        // Invalidate query to refresh data
        queryClient.invalidateQueries({ queryKey: ["tasks"] });
      }
    } catch (error) {
      setErrorData({
        title: `Error updating ${showSubscriptions ? "subscription" : "task"}`,
        list: [(error as Error).message],
      });
    }
  };

  const handleEditTask = (taskId: string) => {
    const taskToEdit = taskData.find((task) => task.id === taskId);
    if (taskToEdit) {
      setSelectedTaskToEdit(taskToEdit);
      setEditFormData({
        title: taskToEdit.title,
        description: taskToEdit.description,
        category: taskToEdit.category,
        state: taskToEdit.state,
        status: taskToEdit.status,
      });
      setIsEditTaskDialogOpen(true);
    }
  };

  const handleEditFormChange = (field: string, value: string) => {
    setEditFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSaveEditedTask = async () => {
    if (!selectedTaskToEdit) return;

    try {
      // Update task via API
      await api.put(
        `${getURL("TASKS")}/${selectedTaskToEdit.id}`,
        editFormData,
      );

      // Update local state
      setTaskData((prevData) =>
        prevData.map((item) =>
          item.id === selectedTaskToEdit.id
            ? { ...item, ...editFormData }
            : item,
        ),
      );

      // Invalidate query to refresh data
      queryClient.invalidateQueries({ queryKey: ["tasks"] });

      // Close dialog
      setIsEditTaskDialogOpen(false);
      setSelectedTaskToEdit(null);
    } catch (error) {
      setErrorData({
        title: "Error updating task",
        list: [(error as Error).message],
      });
    }
  };

  // Function to handle viewing task details
  const handleViewTaskDetails = (task: Task) => {
    // Set the selected text to the task description
    setSelectedText({
      value: task.description,
      title: `Task: ${task.title}`,
    });
    setIsTextDialogOpen(true);
  };

  // Function to handle deleting a single task
  const handleDeleteSingleTask = (taskId: string) => {
    mutateDeleteTask(
      { taskId },
      {
        onError: (error: Error) => {
          setErrorData({
            title: "Error deleting task",
            list: [error.message],
          });
        },
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
        },
      },
    );
  };

  // Function to handle batch edit
  const handleBatchEdit = () => {
    // Reset form data and field selections
    setBatchEditFormData({});
    setBatchEditFields({
      title: false,
      description: false,
      category: false,
      state: false,
      status: false,
    });
    setIsBatchEditDialogOpen(true);
  };

  // Function to handle batch edit form changes
  const handleBatchEditFormChange = (field: string, value: string) => {
    setBatchEditFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Function to toggle which fields to include in batch edit
  const toggleBatchEditField = (field: string) => {
    setBatchEditFields((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  // Function to save batch edits
  const handleSaveBatchEdits = async () => {
    try {
      // Create an object with only the fields that are selected for editing
      const fieldsToUpdate: Partial<Task> = {};
      Object.keys(batchEditFields).forEach((field) => {
        if (
          batchEditFields[field] &&
          batchEditFormData[field as keyof Task] !== undefined
        ) {
          // Use type assertion to fix the type error
          fieldsToUpdate[field as keyof Task] = batchEditFormData[
            field as keyof Task
          ] as any;
        }
      });

      // If no fields are selected, return
      if (Object.keys(fieldsToUpdate).length === 0) {
        setIsBatchEditDialogOpen(false);
        return;
      }

      // Update each selected task
      const updatePromises = selectedRows.map((taskId) =>
        api.put(`${getURL("TASKS")}/${taskId}`, fieldsToUpdate),
      );

      await Promise.all(updatePromises);

      // Update local state
      setTaskData((prevData) =>
        prevData.map((task) =>
          selectedRows.includes(task.id)
            ? { ...task, ...fieldsToUpdate }
            : task,
        ),
      );

      // Invalidate query to refresh data
      queryClient.invalidateQueries({ queryKey: ["tasks"] });

      // Close dialog
      setIsBatchEditDialogOpen(false);
    } catch (error) {
      setErrorData({
        title: "Error updating tasks",
        list: [(error as Error).message],
      });
    }
  };

  const taskColDefs: ColDef[] = [
    {
      headerName: "Actions",
      field: "actions",
      flex: 1,
      sortable: false,
      cellRenderer: (params: any) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => e.stopPropagation()}
              title="Task actions"
            >
              <ForwardedIconComponent name="MoreVertical" className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={() => handleEditTask(params.data.id)}
              className="cursor-pointer"
            >
              <ForwardedIconComponent name="Edit" className="mr-2 h-4 w-4" />
              Edit Task
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => handleViewTaskDetails(params.data)}
              className="cursor-pointer"
            >
              <ForwardedIconComponent name="Eye" className="mr-2 h-4 w-4" />
              View Details
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => handleDeleteSingleTask(params.data.id)}
              className="cursor-pointer text-red-600 focus:text-red-600"
            >
              <ForwardedIconComponent name="Trash2" className="mr-2 h-4 w-4" />
              Delete Task
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
      editable: false,
    },
    {
      headerName: "ID",
      field: "id",
      flex: 1,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "id" }),
      editable: false,
    },
    {
      headerName: "Title",
      field: "title",
      flex: 2,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "title" }),
      editable: true,
    },
    {
      headerName: "Description",
      field: "description",
      flex: 3,
      sortable: true,
      cellRenderer: DescriptionRenderer,
      editable: true,
    },
    {
      headerName: "Category",
      field: "category",
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "State",
      field: "state",
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "Status",
      field: "status",
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "Result",
      field: "result",
      flex: 2,
      sortable: false,
      cellRenderer: ResultRenderer,
      editable: false,
    },
    {
      headerName: "Created At",
      field: "created_at",
      flex: 1,
      sortable: true,
      sort: "desc",
      cellRenderer: DateRenderer,
      editable: false,
    },
    {
      headerName: "Updated At",
      field: "updated_at",
      flex: 1,
      sortable: true,
      cellRenderer: DateRenderer,
      editable: false,
    },
  ];

  const subscriptionColDefs: ColDef[] = [
    {
      headerName: "ID",
      field: "id",
      flex: 1,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "id" }),
      editable: false,
    },
    {
      headerName: "Flow ID",
      field: "flow_id",
      flex: 2,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "flow id" }),
      editable: false,
    },
    {
      headerName: "Event Type",
      field: "event_type",
      flex: 2,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "event type" }),
      editable: true,
    },
    {
      headerName: "Category",
      field: "category",
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "State",
      field: "state",
      flex: 2,
      sortable: true,
      cellRenderer: (params: any) => {
        // If state is a string that looks like JSON, parse it and use ResultRenderer
        if (params.value && typeof params.value === "string") {
          try {
            // Check if it starts with { or [ to determine if it's likely JSON
            if (
              params.value.trim().startsWith("{") ||
              params.value.trim().startsWith("[")
            ) {
              const jsonState = JSON.parse(params.value);
              return ResultRenderer({ value: jsonState });
            }
          } catch (e) {
            // If parsing fails, it's not JSON
          }
        }
        // If it's not JSON or parsing failed, use the BadgeRenderer
        return BadgeRenderer(params);
      },
      editable: true,
    },
    {
      headerName: "Created At",
      field: "created_at",
      flex: 1,
      sortable: true,
      sort: "desc",
      cellRenderer: DateRenderer,
      editable: false,
    },
    {
      headerName: "Updated At",
      field: "updated_at",
      flex: 1,
      sortable: true,
      cellRenderer: DateRenderer,
      editable: false,
    },
  ];

  function handleFilterItems(input: string) {
    setInputValue(input);
  }

  async function removeItems() {
    if (showSubscriptions) {
      selectedRows.forEach(async (subscriptionId) => {
        mutateDeleteSubscription(
          { subscriptionId },
          {
            onError: (error: Error) => {
              setErrorData({
                title: `Error deleting subscription`,
                list: [error.message],
              });
            },
            onSuccess: () => {
              queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
            },
          },
        );
      });
    } else {
      selectedRows.forEach(async (taskId) => {
        mutateDeleteTask(
          { taskId },
          {
            onError: (error: Error) => {
              setErrorData({
                title: `Error deleting task`,
                list: [error.message],
              });
            },
            onSuccess: () => {
              queryClient.invalidateQueries({ queryKey: ["tasks"] });
            },
          },
        );
      });
    }
  }

  const isFetchingTasks = !!useIsFetching({
    queryKey: ["tasks"],
    exact: false,
  });

  const isFetchingSubscriptions = !!useIsFetching({
    queryKey: ["subscriptions"],
    exact: false,
  });

  const error = showSubscriptions ? subscriptionsError : tasksError;
  const isLoading = showSubscriptions ? isLoadingSubscriptions : isLoadingTasks;

  // Function to format JSON with syntax highlighting
  const formatJSON = (json: any): JSX.Element => {
    if (!json) return <></>;

    const jsonString = JSON.stringify(json, null, 2);

    // Simple syntax highlighting
    return (
      <>
        {jsonString.split("\n").map((line, i) => {
          // Highlight keys (anything before a colon)
          const keyHighlighted = line.replace(
            /(".*?"):/g,
            '<span class="text-blue-500">$1</span>:',
          );

          // Highlight string values (anything in quotes after a colon)
          const valueHighlighted = keyHighlighted.replace(
            /: (".*?")([,]?$)/g,
            ': <span class="text-green-500">$1</span>$2',
          );

          // Highlight numbers
          const numberHighlighted = valueHighlighted.replace(
            /: (\d+)([,]?$)/g,
            ': <span class="text-purple-500">$1</span>$2',
          );

          // Highlight booleans and null
          const boolHighlighted = numberHighlighted.replace(
            /: (true|false|null)([,]?$)/g,
            ': <span class="text-yellow-500">$1</span>$2',
          );

          return (
            <div
              key={i}
              dangerouslySetInnerHTML={{ __html: boolHighlighted }}
              className="whitespace-pre"
            />
          );
        })}
      </>
    );
  };

  // Function to check if the result contains markdown content
  const hasMarkdownContent = (result: any): boolean => {
    // Skip if result is null or undefined
    if (!result) return false;

    // Check if result has the structure with message.data.text (task output)
    if (
      result.outputs &&
      result.outputs.length > 0 &&
      result.outputs[0].value &&
      result.outputs[0].value.message &&
      result.outputs[0].value.message.data &&
      typeof result.outputs[0].value.message.data.text === "string"
    ) {
      return true;
    }

    // For subscription state or other data, check if it contains markdown-like content
    if (typeof result === "string") {
      // Check if the string contains markdown indicators like # or *
      return /^#|^\*|\n#|\n\*/.test(result);
    }

    return false;
  };

  // Function to get markdown content from result
  const getMarkdownContent = (result: any): string => {
    if (!result) return "";

    // For task outputs with message.data.text
    if (
      result.outputs &&
      result.outputs.length > 0 &&
      result.outputs[0].value &&
      result.outputs[0].value.message &&
      result.outputs[0].value.message.data &&
      typeof result.outputs[0].value.message.data.text === "string"
    ) {
      return result.outputs[0].value.message.data.text;
    }

    // For subscription state or other string data
    if (typeof result === "string") {
      return result;
    }

    return "";
  };

  if (error) {
    return (
      <div>
        Error loading {showSubscriptions ? "subscriptions" : "tasks"}:{" "}
        {(error as Error).message}
      </div>
    );
  }

  return (
    <>
      <PageLayout
        title={showSubscriptions ? "Subscriptions" : "Tasks"}
        description={
          showSubscriptions
            ? "Manage flow subscriptions to events."
            : "Manage and track your tasks efficiently."
        }
        button={
          <div className="flex gap-2">
            {!showSubscriptions && (
              <>
                <AddNewTaskButton asChild>
                  <Button variant="primary">
                    <ForwardedIconComponent name="Plus" className="w-4" />
                    Add New Task
                  </Button>
                </AddNewTaskButton>
                {selectedRows.length > 1 && (
                  <Button variant="outline" onClick={handleBatchEdit}>
                    <ForwardedIconComponent
                      name="Edit2"
                      className="mr-2 h-4 w-4"
                    />
                    Batch Edit ({selectedRows.length})
                  </Button>
                )}
              </>
            )}
          </div>
        }
      >
        <div className="flex h-full w-full flex-col space-y-8 pb-8">
          <div className="flex w-full justify-between px-4 py-4">
            <div className="flex w-96 items-center gap-4">
              <Input
                placeholder={
                  showSubscriptions ? "Search Subscriptions" : "Search Tasks"
                }
                value={inputValue}
                onChange={(e) => handleFilterItems(e.target.value)}
              />
              {inputValue && (
                <ForwardedIconComponent
                  name="X"
                  className="cursor-pointer"
                  onClick={() => handleFilterItems("")}
                />
              )}
            </div>
            <div className="flex items-center gap-2">
              <span>Tasks</span>
              <Switch
                checked={showSubscriptions}
                onCheckedChange={setShowSubscriptions}
              />
              <span>Subscriptions</span>
            </div>
          </div>
          {isLoading ? (
            <div className="flex h-full w-full items-center justify-center">
              <LoadingComponent remSize={12} />
            </div>
          ) : (
            <div className="flex h-full w-full flex-col justify-between">
              <TableComponent
                key={showSubscriptions ? "subscriptions" : "tasks"}
                rowData={showSubscriptions ? subscriptionData : taskData}
                columnDefs={
                  showSubscriptions ? subscriptionColDefs : taskColDefs
                }
                onSelectionChanged={(event: any) => {
                  setSelectedRows(
                    event.api.getSelectedRows().map((row: any) => row.id),
                  );
                }}
                rowSelection="multiple"
                pagination={true}
                onDelete={removeItems}
                quickFilterText={inputValue}
                editable={true}
                onCellEditRequest={handleCellEditRequest}
                defaultColDef={{
                  sortable: true,
                  resizable: true,
                }}
                onGridReady={(params) => {
                  // Set default sorting by created_at in descending order
                  params.api.setSortModel([
                    {
                      colId: "created_at",
                      sort: "desc",
                    },
                  ]);
                }}
              />
            </div>
          )}
        </div>
      </PageLayout>

      {/* Result Dialog */}
      <Dialog open={isResultDialogOpen} onOpenChange={setIsResultDialogOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[800px]">
          <DialogHeader>
            <DialogTitle>
              {selectedResult?.error
                ? "Error Details"
                : hasMarkdownContent(selectedResult)
                  ? "Task Result - Markdown Content"
                  : selectedResult?.outputs
                    ? "Task Results"
                    : "Task Result"}
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            {selectedResult && (
              <div className="relative">
                <div className="absolute right-2 top-2 flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      // Copy appropriate content based on type
                      const contentToCopy = hasMarkdownContent(selectedResult)
                        ? getMarkdownContent(selectedResult)
                        : JSON.stringify(selectedResult, null, 2);

                      navigator.clipboard.writeText(contentToCopy);
                      setResultCopyFeedback(true);
                      setTimeout(() => setResultCopyFeedback(false), 2000);
                    }}
                    title="Copy to clipboard"
                  >
                    {resultCopyFeedback ? (
                      <span className="flex items-center">
                        <ForwardedIconComponent
                          name="Check"
                          className="mr-1 h-4 w-4 text-green-500"
                        />
                        Copied!
                      </span>
                    ) : (
                      <span className="flex items-center">
                        <ForwardedIconComponent
                          name="Copy"
                          className="mr-1 h-4 w-4"
                        />
                        Copy
                      </span>
                    )}
                  </Button>
                </div>

                {hasMarkdownContent(selectedResult) ? (
                  <div className="prose max-w-none overflow-x-auto rounded-md bg-white p-4 pt-12 dark:prose-invert dark:bg-gray-900">
                    <Markdown>{getMarkdownContent(selectedResult)}</Markdown>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-md bg-gray-100 p-4 pt-12 font-mono text-sm dark:bg-gray-800">
                    {formatJSON(selectedResult)}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={() => setIsResultDialogOpen(false)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Text Dialog */}
      <Dialog open={isTextDialogOpen} onOpenChange={setIsTextDialogOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[800px]">
          <DialogHeader>
            <DialogTitle>{selectedText.title}</DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            <div className="relative">
              <div className="absolute right-2 top-2 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(selectedText.value);
                    setTextCopyFeedback(true);
                    setTimeout(() => setTextCopyFeedback(false), 2000);
                  }}
                  title="Copy to clipboard"
                >
                  {textCopyFeedback ? (
                    <span className="flex items-center">
                      <ForwardedIconComponent
                        name="Check"
                        className="mr-1 h-4 w-4 text-green-500"
                      />
                      Copied!
                    </span>
                  ) : (
                    <span className="flex items-center">
                      <ForwardedIconComponent
                        name="Copy"
                        className="mr-1 h-4 w-4"
                      />
                      Copy
                    </span>
                  )}
                </Button>
              </div>
              <div className="overflow-x-auto whitespace-pre-wrap rounded-md bg-white p-4 pt-12 dark:bg-gray-900">
                {/* Check if description contains markdown and render accordingly */}
                {hasMarkdownContent(selectedText.value) ? (
                  <div className="prose max-w-none dark:prose-invert">
                    <Markdown>{selectedText.value}</Markdown>
                  </div>
                ) : (
                  <p>{selectedText.value}</p>
                )}
              </div>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={() => setIsTextDialogOpen(false)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* New Edit Task Dialog */}
      <Dialog
        open={isEditTaskDialogOpen}
        onOpenChange={setIsEditTaskDialogOpen}
      >
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Task</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="title" className="text-right">
                Title
              </Label>
              <Input
                id="title"
                value={editFormData.title || ""}
                onChange={(e) => handleEditFormChange("title", e.target.value)}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="description" className="text-right">
                Description
              </Label>
              <Textarea
                id="description"
                value={editFormData.description || ""}
                onChange={(e) =>
                  handleEditFormChange("description", e.target.value)
                }
                className="col-span-3"
                rows={4}
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="category" className="text-right">
                Category
              </Label>
              <Input
                id="category"
                value={editFormData.category || ""}
                onChange={(e) =>
                  handleEditFormChange("category", e.target.value)
                }
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="state" className="text-right">
                State
              </Label>
              <Input
                id="state"
                value={editFormData.state || ""}
                onChange={(e) => handleEditFormChange("state", e.target.value)}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="status" className="text-right">
                Status
              </Label>
              <Select
                value={editFormData.status}
                onValueChange={(value) => handleEditFormChange("status", value)}
              >
                <SelectTrigger className="col-span-3">
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
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsEditTaskDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveEditedTask}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Batch Edit Dialog */}
      <Dialog
        open={isBatchEditDialogOpen}
        onOpenChange={setIsBatchEditDialogOpen}
      >
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Batch Edit Tasks ({selectedRows.length})</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="mb-4 rounded-md bg-amber-50 p-3 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
              <p className="flex items-center text-sm">
                <ForwardedIconComponent name="Info" className="mr-2 h-4 w-4" />
                Select which fields to update for all selected tasks. Only
                checked fields will be modified.
              </p>
            </div>

            <div className="grid grid-cols-5 items-center gap-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="edit-title"
                  checked={batchEditFields.title}
                  onChange={() => toggleBatchEditField("title")}
                  className="mr-2"
                />
                <Label htmlFor="edit-title" className="text-right">
                  Title
                </Label>
              </div>
              <Input
                id="batch-title"
                value={batchEditFormData.title || ""}
                onChange={(e) =>
                  handleBatchEditFormChange("title", e.target.value)
                }
                className="col-span-4"
                disabled={!batchEditFields.title}
              />
            </div>

            <div className="grid grid-cols-5 items-center gap-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="edit-description"
                  checked={batchEditFields.description}
                  onChange={() => toggleBatchEditField("description")}
                  className="mr-2"
                />
                <Label htmlFor="edit-description" className="text-right">
                  Description
                </Label>
              </div>
              <Textarea
                id="batch-description"
                value={batchEditFormData.description || ""}
                onChange={(e) =>
                  handleBatchEditFormChange("description", e.target.value)
                }
                className="col-span-4"
                rows={4}
                disabled={!batchEditFields.description}
              />
            </div>

            <div className="grid grid-cols-5 items-center gap-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="edit-category"
                  checked={batchEditFields.category}
                  onChange={() => toggleBatchEditField("category")}
                  className="mr-2"
                />
                <Label htmlFor="edit-category" className="text-right">
                  Category
                </Label>
              </div>
              <Input
                id="batch-category"
                value={batchEditFormData.category || ""}
                onChange={(e) =>
                  handleBatchEditFormChange("category", e.target.value)
                }
                className="col-span-4"
                disabled={!batchEditFields.category}
              />
            </div>

            <div className="grid grid-cols-5 items-center gap-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="edit-state"
                  checked={batchEditFields.state}
                  onChange={() => toggleBatchEditField("state")}
                  className="mr-2"
                />
                <Label htmlFor="edit-state" className="text-right">
                  State
                </Label>
              </div>
              <Input
                id="batch-state"
                value={batchEditFormData.state || ""}
                onChange={(e) =>
                  handleBatchEditFormChange("state", e.target.value)
                }
                className="col-span-4"
                disabled={!batchEditFields.state}
              />
            </div>

            <div className="grid grid-cols-5 items-center gap-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="edit-status"
                  checked={batchEditFields.status}
                  onChange={() => toggleBatchEditField("status")}
                  className="mr-2"
                />
                <Label htmlFor="edit-status" className="text-right">
                  Status
                </Label>
              </div>
              <div className="col-span-4">
                <Select
                  value={batchEditFormData.status}
                  onValueChange={(value) =>
                    handleBatchEditFormChange("status", value)
                  }
                  disabled={!batchEditFields.status}
                >
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
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsBatchEditDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveBatchEdits}>
              Apply to {selectedRows.length} Tasks
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
