import ForwardedIconComponent from "@/components/common/genericIconComponent";
import LoadingComponent from "@/components/common/loadingComponent";
import PageLayout from "@/components/common/pageLayout";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuTrigger } from "@/components/ui/context-menu";
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
import { useGetActors } from "@/controllers/API/queries/actors";
import { useDeleteSubscription } from "@/controllers/API/queries/subscriptions/use-delete-subscription";
import { useGetSubscriptions } from "@/controllers/API/queries/subscriptions/use-get-subscriptions";
import { useDeleteTask } from "@/controllers/API/queries/tasks/use-delete-task";
import { useGetTasks } from "@/controllers/API/queries/tasks/use-get-tasks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { Subscription } from "@/types/Subscription";
import { ReviewInfo, Task } from "@/types/Task";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { CellEditRequestEvent, ColDef } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import AddNewTaskButton from "./components/AddNewTaskButton";
import TaskActionsMenu from "./components/TaskActionsMenu";

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
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [editModalOpen, setEditModalOpen] = useState<boolean>(false);
  const [taskToEdit, setTaskToEdit] = useState<Task | null>(null);
  const [isReviewTaskDialogOpen, setIsReviewTaskDialogOpen] = useState(false);
  const [selectedTaskToReview, setSelectedTaskToReview] = useState<Task | null>(
    null,
  );
  const [reviewFormData, setReviewFormData] = useState({
    comment: "",
  });
  const [isReviewsDialogOpen, setIsReviewsDialogOpen] = useState(false);
  const [selectedTaskForReviews, setSelectedTaskForReviews] =
    useState<Task | null>(null);
  const [editingReviewIndex, setEditingReviewIndex] = useState<number | null>(
    null,
  );
  const [editReviewFormData, setEditReviewFormData] = useState({
    comment: "",
  });

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

  const { data: actors } = useGetActors();
  const { mutate: mutateDeleteTask } = useDeleteTask();
  const { mutate: mutateDeleteSubscription } = useDeleteSubscription();

  const actorsList = useMemo(() => {
    return Array.isArray(actors) ? actors : [];
  }, [actors]);

  useEffect(() => {
    if (tasks && Array.isArray(tasks) && !showSubscriptions) {
      // Sort tasks by created_at in descending order (newest first)
      const sortedTasks = [...tasks].sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return dateB - dateA;
      });
      setTaskData(sortedTasks);
    }
  }, [tasks, showSubscriptions]);

  useEffect(() => {
    if (subscriptions && Array.isArray(subscriptions) && showSubscriptions) {
      // Sort subscriptions by created_at in descending order (newest first)
      const sortedSubscriptions = [...subscriptions].sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return dateB - dateA;
      });
      setSubscriptionData(sortedSubscriptions);
    }
  }, [subscriptions, showSubscriptions]);

  const BadgeRenderer = (props: { value: string; rowData?: any }) => {
    if (!props.value) return null;

    // If it's a long string, truncate it for display in the badge
    const displayValue =
      typeof props.value === "string" && props.value.length > 20
        ? props.value.substring(0, 20) + "..."
        : props.value;

    // Check if this row has review data (for the Status column)
    const hasReview = props.rowData && props.rowData.review;
    const hasReviewHistory =
      props.rowData &&
      props.rowData.review_history &&
      props.rowData.review_history.length > 0;

    // If it's the status column and has a review, show a special badge
    if (hasReview && props.value === "pending") {
      return (
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="bg-amber-50 text-amber-900 dark:bg-amber-900/20 dark:text-amber-400"
          >
            {displayValue}
          </Badge>
          <Badge
            variant="secondary"
            className="bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-400"
          >
            Under Review
          </Badge>
        </div>
      );
    }

    // If it has review history but is not currently under review, show a different badge
    if (
      hasReviewHistory &&
      props.value !== "pending" &&
      props.value !== "completed"
    ) {
      return (
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="bg-gray-50 text-gray-900 dark:bg-gray-800 dark:text-gray-200"
          >
            {displayValue}
          </Badge>
          <Badge
            variant="secondary"
            className="bg-blue-100 text-blue-900 dark:bg-blue-900/30 dark:text-blue-400"
          >
            Previously Reviewed
          </Badge>
        </div>
      );
    }

    // For regular status badges, add appropriate colors
    let badgeClasses =
      "bg-gray-50 text-gray-900 dark:bg-gray-800 dark:text-gray-200";
    if (props.value === "completed") {
      badgeClasses =
        "bg-green-50 text-green-900 dark:bg-green-900/20 dark:text-green-400";
    } else if (props.value === "failed") {
      badgeClasses =
        "bg-red-50 text-red-900 dark:bg-red-900/20 dark:text-red-400";
    } else if (props.value === "processing") {
      badgeClasses =
        "bg-blue-50 text-blue-900 dark:bg-blue-900/20 dark:text-blue-400";
    }

    return (
      <Badge variant="outline" className={badgeClasses}>
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

  const handleEditTask = useCallback(
    (taskId: string) => {
      const task = tasks?.find((t) => t.id === taskId);
      if (task) {
        setTaskToEdit(task);
        setEditModalOpen(true);
      }
    },
    [tasks],
  );

  const handleTaskUpdate = useCallback((updatedTask: Task) => {
    setEditModalOpen(false);
    setTaskToEdit(null);
  }, []);

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
    // Also set the selectedTaskToEdit to show review info
    setSelectedTaskToEdit(task);
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

  // ActorRenderer component
  const ActorRenderer = ({
    actorId,
    entityColor,
  }: {
    actorId: string;
    entityColor?: boolean;
  }) => {
    const actor = actorsList.find((a) => a.id === actorId);

    if (!actor) {
      return <span className="text-sm text-muted-foreground">Unknown</span>;
    }

    return (
      <div className="flex items-center gap-2">
        <div
          className="flex-shrink-0"
          style={{ width: "24px", height: "24px" }}
        >
          <ForwardedIconComponent
            name={actor.entity_type === "user" ? "User" : "Workflow"}
            className={`h-full w-full ${
              entityColor && actor.entity_type === "user"
                ? "text-blue-600"
                : actor.entity_type === "flow"
                  ? "text-emerald-600"
                  : "text-slate-600 dark:text-slate-400"
            }`}
            strokeWidth={1.75}
          />
        </div>
        <span className="truncate text-sm">
          {actor.name || (actor.entity_type === "user" ? "User" : "Flow")}
        </span>
      </div>
    );
  };

  // Function to prepare the cell editor options
  const getActorOptions = useCallback(() => {
    if (!Array.isArray(actorsList)) return [];

    return actorsList.map((actor) => ({
      value: actor.id,
      label: `${actor.name || (actor.entity_type === "user" ? "User" : "Flow")} (${actor.entity_type})`,
    }));
  }, [actorsList]);

  // Create a ReviewCountRenderer component
  const ReviewCountRenderer = (props: { data: any }) => {
    const reviewCount = props.data?.review_history?.length || 0;

    const handleClick = () => {
      setSelectedTaskForReviews(props.data);
      setIsReviewsDialogOpen(true);
    };

    if (reviewCount === 0) {
      return (
        <div
          className="flex cursor-pointer items-center justify-center hover:text-blue-600"
          onClick={handleClick}
          title="Click to add reviews"
        >
          <span className="text-gray-400">-</span>
        </div>
      );
    }

    return (
      <div
        className="flex cursor-pointer items-center justify-center rounded-full p-1 hover:bg-purple-200"
        onClick={handleClick}
        title="Click to view or manage reviews"
      >
        <Badge variant="secondary" className="bg-purple-100 text-purple-800">
          <ForwardedIconComponent
            name="MessageSquare"
            className="mr-1 h-3 w-3"
          />
          {reviewCount}
        </Badge>
      </div>
    );
  };

  // Function to handle editing a review
  const handleEditReview = (reviewIndex: number) => {
    if (!selectedTaskForReviews || !selectedTaskForReviews.review_history)
      return;

    const review = selectedTaskForReviews.review_history[reviewIndex];
    setEditingReviewIndex(reviewIndex);
    setEditReviewFormData({
      comment: review.comment,
    });
  };

  // Function to save edited review
  const handleSaveEditedReview = async () => {
    if (!selectedTaskForReviews || editingReviewIndex === null) return;

    try {
      // Create a copy of the review history
      const updatedReviewHistory = [
        ...(selectedTaskForReviews.review_history || []),
      ];

      // Get the original review
      const originalReview = updatedReviewHistory[editingReviewIndex];

      // Update the review at the specified index, ensuring UUID is converted to string
      updatedReviewHistory[editingReviewIndex] = {
        ...originalReview,
        comment: editReviewFormData.comment,
        reviewer_id: String(originalReview.reviewer_id || ""), // Convert to string, use empty string as fallback
        reviewed_at: originalReview.reviewed_at,
      };

      // Update task via API
      await api.put(`${getURL("TASKS")}/${selectedTaskForReviews.id}`, {
        review_history: updatedReviewHistory,
      });

      // Update local state
      setTaskData((prevData) =>
        prevData.map((item) =>
          item.id === selectedTaskForReviews.id
            ? ({ ...item, review_history: updatedReviewHistory } as Task) // Type assertion to ensure compatibility
            : item,
        ),
      );

      // Invalidate query to refresh data
      queryClient.invalidateQueries({ queryKey: ["tasks"] });

      // Reset editing state
      setEditingReviewIndex(null);
      setEditReviewFormData({ comment: "" });

      // Show success message
      const alertStore = useAlertStore.getState();
      alertStore.setSuccessData({
        title: "Review updated successfully",
      });
    } catch (error) {
      setErrorData({
        title: "Error updating review",
        list: [(error as Error).message],
      });
    }
  };

  // Function to get all reviews (current review + review history)
  const getAllReviews = (task: Task): ReviewInfo[] => {
    const reviews: ReviewInfo[] = [];

    // Add review history items if they exist
    if (task.review_history && task.review_history.length > 0) {
      reviews.push(...task.review_history);
    }

    // Add current review if it exists and isn't already in the history
    if (task.review) {
      // Check if the current review is already in the history
      const isReviewInHistory = reviews.some(
        (r) =>
          r.comment === task.review?.comment &&
          r.reviewer_id === task.review?.reviewer_id &&
          r.reviewed_at === task.review?.reviewed_at,
      );

      if (!isReviewInHistory) {
        reviews.push(task.review);
      }
    }

    // Sort by reviewed_at date (newest first)
    return reviews.sort(
      (a, b) =>
        new Date(b.reviewed_at).getTime() - new Date(a.reviewed_at).getTime(),
    );
  };

  // Function to handle reviewing a task
  const handleReviewTask = (task: Task) => {
    setSelectedTaskToReview(task);
    setReviewFormData({ comment: "" });
    setIsReviewTaskDialogOpen(true);
  };

  // Function to handle review form changes
  const handleReviewFormChange = (field: string, value: string) => {
    setReviewFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Function to submit a review
  const handleSubmitReview = async () => {
    if (!selectedTaskToReview) return;

    try {
      // Get the current user ID (first actor in the list or null)
      const reviewerId = actorsList.length > 0 ? actorsList[0].id : "";

      // Create the new review entry
      const newReview = {
        comment: reviewFormData.comment,
        reviewer_id: String(reviewerId), // Always convert to string
        reviewed_at: new Date().toISOString(),
      };

      // Get all existing reviews
      const existingReviews = getAllReviews(selectedTaskToReview);

      // Create review data with comment and update task status to pending
      const reviewData = {
        status: "pending",
        review: newReview,
        review_history: [newReview, ...existingReviews],
      };

      // Update task via API
      await api.put(
        `${getURL("TASKS")}/${selectedTaskToReview.id}`,
        reviewData,
      );

      // Update local state
      setTaskData((prevData) =>
        prevData.map((item) =>
          item.id === selectedTaskToReview.id
            ? ({
                ...item,
                status: "pending",
                review: newReview,
                review_history: reviewData.review_history,
              } as Task) // Type assertion to ensure compatibility
            : item,
        ),
      );

      // Invalidate query to refresh data
      queryClient.invalidateQueries({ queryKey: ["tasks"] });

      // Close dialog if this is not from the Reviews Dialog
      if (
        !selectedTaskForReviews ||
        selectedTaskForReviews.id !== selectedTaskToReview.id
      ) {
        setIsReviewTaskDialogOpen(false);
        setSelectedTaskToReview(null);
      } else {
        // Reset the form
        setReviewFormData({ comment: "" });
      }

      // If this review was initiated from the Reviews Dialog, refresh that data
      if (
        selectedTaskForReviews &&
        selectedTaskForReviews.id === selectedTaskToReview.id
      ) {
        // Fetch the updated task data
        const updatedTaskResponse = await api.get(
          `${getURL("TASKS")}/${selectedTaskForReviews.id}`,
        );
        if (updatedTaskResponse.data) {
          setSelectedTaskForReviews(updatedTaskResponse.data);
        }
      }

      // Show success message
      const alertStore = useAlertStore.getState();
      alertStore.setSuccessData({
        title: "Task reviewed successfully",
      });
    } catch (error) {
      setErrorData({
        title: "Error reviewing task",
        list: [(error as Error).message],
      });
    }
  };

  const taskColDefs: ColDef[] = [
    {
      headerName: "Actions",
      field: "actions",
      width: 80,
      minWidth: 80,
      maxWidth: 80,
      sortable: false,
      cellRenderer: (params: any) => (
        <div className="flex items-center justify-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 rounded-full text-slate-600 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-950/50 dark:hover:text-slate-300"
                title="Actions"
              >
                <ForwardedIconComponent
                  name="MoreHorizontal"
                  className="h-4 w-4"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="flex cursor-pointer items-center gap-2"
                onClick={() => handleEditTask(params.data.id)}
              >
                <ForwardedIconComponent
                  name="Pencil"
                  className="h-4 w-4"
                  aria-hidden="true"
                />
                <span>Edit</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex cursor-pointer items-center gap-2"
                onClick={() => handleViewTaskDetails(params.data)}
              >
                <ForwardedIconComponent
                  name="Eye"
                  className="h-4 w-4"
                  aria-hidden="true"
                />
                <span>View Details</span>
              </DropdownMenuItem>
              {params.data.status === "completed" && (
                <DropdownMenuItem
                  className="flex cursor-pointer items-center gap-2"
                  onClick={() => handleReviewTask(params.data)}
                >
                  <ForwardedIconComponent
                    name="CheckCheck"
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                  <span>Review</span>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                onClick={() => handleDeleteSingleTask(params.data.id)}
              >
                <ForwardedIconComponent
                  name="Trash2"
                  className="h-4 w-4"
                  aria-hidden="true"
                />
                <span>Delete</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
      editable: false,
    },
    {
      headerName: "ID",
      field: "id",
      minWidth: 220,
      flex: 1,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "id" }),
      editable: false,
    },
    {
      headerName: "Title",
      field: "title",
      minWidth: 200,
      flex: 2,
      sortable: true,
      cellRenderer: (params: any) =>
        TextRenderer({ value: params.value, fieldName: "title" }),
      editable: true,
    },
    {
      headerName: "Author",
      field: "author_id",
      minWidth: 180,
      flex: 1,
      sortable: true,
      cellRenderer: (params: any) => <ActorRenderer actorId={params.value} />,
      editable: true,
      cellEditor: "agSelectCellEditor",
      cellEditorParams: {
        values: getActorOptions().map((option) => option.value),
      },
      valueFormatter: (params) => {
        const actor = actorsList.find((a) => a.id === params.value);
        return actor
          ? `${actor.name || (actor.entity_type === "user" ? "User" : "Flow")} (${actor.entity_type})`
          : "Unknown";
      },
    },
    {
      headerName: "Assignee",
      field: "assignee_id",
      minWidth: 180,
      flex: 1,
      sortable: true,
      cellRenderer: (params: any) => (
        <ActorRenderer actorId={params.value} entityColor={true} />
      ),
      editable: true,
      cellEditor: "agSelectCellEditor",
      cellEditorParams: {
        values: getActorOptions().map((option) => option.value),
      },
      valueFormatter: (params) => {
        const actor = actorsList.find((a) => a.id === params.value);
        return actor
          ? `${actor.name || (actor.entity_type === "user" ? "User" : "Flow")} (${actor.entity_type})`
          : "Unknown";
      },
    },
    {
      headerName: "Description",
      field: "description",
      minWidth: 300,
      flex: 3,
      sortable: true,
      cellRenderer: DescriptionRenderer,
      editable: true,
    },
    {
      headerName: "Category",
      field: "category",
      minWidth: 140,
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "State",
      field: "state",
      minWidth: 140,
      flex: 1,
      sortable: true,
      cellRenderer: BadgeRenderer,
      editable: true,
    },
    {
      headerName: "Status",
      field: "status",
      width: 300,
      minWidth: 300,
      maxWidth: 300,
      sortable: true,
      suppressSizeToFit: true,
      resizable: false,
      cellRenderer: (params: any) =>
        BadgeRenderer({ value: params.value, rowData: params.data }),
      editable: true,
    },
    {
      headerName: "Reviews",
      field: "review_history",
      width: 100,
      minWidth: 100,
      maxWidth: 100,
      sortable: true,
      cellRenderer: ReviewCountRenderer,
      editable: false,
    },
    {
      headerName: "Result",
      field: "result",
      minWidth: 200,
      flex: 2,
      sortable: false,
      cellRenderer: ResultRenderer,
      editable: false,
    },
    {
      headerName: "Created At",
      field: "created_at",
      minWidth: 180,
      flex: 1,
      sortable: true,
      cellRenderer: DateRenderer,
      editable: false,
    },
    {
      headerName: "Updated At",
      field: "updated_at",
      minWidth: 180,
      flex: 1,
      sortable: true,
      sort: "desc",
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
                <AddNewTaskButton
                  initialData={taskToEdit ?? undefined}
                  mode={taskToEdit ? "edit" : "create"}
                  onUpdate={handleTaskUpdate}
                  openFromParent={editModalOpen}
                  setOpenFromParent={setEditModalOpen}
                >
                  <Button
                    variant="default"
                    size="sm"
                    className="md:w-auto"
                    data-testid="create-task-button"
                  >
                    <ForwardedIconComponent
                      name="Plus"
                      className="mr-2 h-4 w-4"
                      aria-hidden="true"
                    />
                    New Task
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
              <div className="flex-1 overflow-auto">
                <ContextMenu>
                  <ContextMenuTrigger>
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
                        params.api.applyColumnState({
                          state: [
                            {
                              colId: "created_at",
                              sort: "desc",
                            },
                          ],
                        });
                      }}
                      getRowClass={(params) => {
                        if (showSubscriptions) return "";

                        // For tasks, style based on assignee type
                        const task = params.data as Task;
                        if (!task || !task.assignee_id) return "";

                        const assigneeActor = actorsList.find(
                          (a) => a.id === task.assignee_id,
                        );

                        if (assigneeActor) {
                          return assigneeActor.entity_type === "user"
                            ? "bg-blue-50 dark:bg-blue-950/30"
                            : "";
                        }

                        return "";
                      }}
                      onRowContextMenu={(event) => {
                        setSelectedTaskId(event.data.id);
                      }}
                    />
                  </ContextMenuTrigger>
                  <TaskActionsMenu
                    taskId={selectedTaskId}
                    onClose={() => setSelectedTaskId(null)}
                    onEdit={handleEditTask}
                    onReview={(taskId) => {
                      const task = tasks?.find((t) => t.id === taskId);
                      if (task) {
                        handleReviewTask(task);
                      }
                    }}
                  />
                </ContextMenu>
              </div>
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

                {/* If this is a task with review data, show it */}
                {selectedTaskToEdit?.review && (
                  <div className="mt-6 border-t pt-4">
                    <h3 className="text-lg font-semibold">
                      Review Information
                    </h3>
                    <div className="mt-2 space-y-2">
                      <div>
                        <span className="font-medium">Reviewer:</span>{" "}
                        {actorsList.find(
                          (a) =>
                            a.id === selectedTaskToEdit.review?.reviewer_id,
                        )?.name || "Unknown"}
                      </div>
                      <div>
                        <span className="font-medium">Review Date:</span>{" "}
                        {selectedTaskToEdit.review?.reviewed_at
                          ? new Date(
                              selectedTaskToEdit.review.reviewed_at,
                            ).toLocaleString()
                          : "N/A"}
                      </div>
                      <div>
                        <span className="font-medium">Comment:</span>
                        <p className="mt-1 rounded bg-gray-50 p-2 dark:bg-gray-800">
                          {selectedTaskToEdit.review?.comment}
                        </p>
                      </div>

                      {/* Show review history if available */}
                      {selectedTaskToEdit.review_history &&
                        selectedTaskToEdit.review_history.length > 1 && (
                          <div className="mt-4">
                            <h4 className="text-md font-semibold">
                              Review History
                            </h4>
                            <div className="mt-2 max-h-60 overflow-y-auto rounded border border-gray-200 dark:border-gray-700">
                              {selectedTaskToEdit.review_history
                                .slice(0, -1)
                                .map((review, index) => (
                                  <div
                                    key={index}
                                    className="border-b border-gray-200 p-3 last:border-b-0 dark:border-gray-700"
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="font-medium">
                                        {actorsList.find(
                                          (a) => a.id === review.reviewer_id,
                                        )?.name || "Unknown"}
                                      </span>
                                      <span className="text-sm text-gray-500">
                                        {new Date(
                                          review.reviewed_at,
                                        ).toLocaleString()}
                                      </span>
                                    </div>
                                    <p className="mt-1 text-sm">
                                      {review.comment}
                                    </p>
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}
                    </div>
                  </div>
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

      {/* Review Task Dialog */}
      <Dialog
        open={isReviewTaskDialogOpen}
        onOpenChange={setIsReviewTaskDialogOpen}
      >
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>Review Task</DialogTitle>
          </DialogHeader>

          {selectedTaskToReview && (
            <div className="grid gap-6 py-4">
              {/* Task Information Section */}
              <div className="rounded-md bg-gray-50 p-4 dark:bg-gray-800">
                <h3 className="mb-2 text-lg font-medium">
                  {selectedTaskToReview.title}
                </h3>
                <div className="mb-2 text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Status:</span>{" "}
                  <Badge
                    variant={
                      selectedTaskToReview.status === "completed"
                        ? "outline"
                        : "outline"
                    }
                  >
                    {selectedTaskToReview.status}
                  </Badge>
                </div>
                <div className="mb-4 text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Description:</span>
                  <p className="mt-1 whitespace-pre-wrap rounded bg-white p-2 text-sm dark:bg-gray-700">
                    {selectedTaskToReview.description}
                  </p>
                </div>

                {/* Task Result Preview */}
                {selectedTaskToReview.result && (
                  <div className="mb-2">
                    <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                      Result:
                    </span>
                    <div className="relative mt-1">
                      <div className="absolute right-2 top-2 z-10">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            // Copy appropriate content based on type
                            const contentToCopy = hasMarkdownContent(
                              selectedTaskToReview.result,
                            )
                              ? getMarkdownContent(selectedTaskToReview.result)
                              : JSON.stringify(
                                  selectedTaskToReview.result,
                                  null,
                                  2,
                                );

                            navigator.clipboard.writeText(contentToCopy);
                            // We don't have a state for this feedback, so we'll use a temporary visual cue
                            const btn =
                              document.activeElement as HTMLButtonElement;
                            if (btn) {
                              const originalText = btn.innerHTML;
                              btn.innerHTML =
                                '<span class="flex items-center"><svg class="mr-1 h-4 w-4 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>Copied!</span>';
                              setTimeout(() => {
                                btn.innerHTML = originalText;
                              }, 2000);
                            }
                          }}
                          title="Copy to clipboard"
                        >
                          <span className="flex items-center">
                            <ForwardedIconComponent
                              name="Copy"
                              className="mr-1 h-4 w-4"
                            />
                            Copy
                          </span>
                        </Button>
                      </div>

                      {hasMarkdownContent(selectedTaskToReview.result) ? (
                        <div className="prose max-w-none overflow-x-auto rounded-md bg-white p-4 pt-12 dark:prose-invert dark:bg-gray-900">
                          <Markdown>
                            {getMarkdownContent(selectedTaskToReview.result)}
                          </Markdown>
                        </div>
                      ) : (
                        <div className="overflow-x-auto rounded-md bg-gray-100 p-4 pt-12 font-mono text-xs dark:bg-gray-800">
                          {formatJSON(selectedTaskToReview.result)}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Review Form */}
              <div>
                <h3 className="text-md mb-3 font-medium">Your Review</h3>
                <div className="grid gap-4">
                  <div>
                    <Label htmlFor="comment" className="mb-2 block">
                      Review Comments
                    </Label>
                    <Textarea
                      id="comment"
                      value={reviewFormData.comment}
                      onChange={(e) =>
                        handleReviewFormChange("comment", e.target.value)
                      }
                      className="min-h-[120px] w-full"
                      placeholder="Provide feedback on this task. What needs to be improved or corrected?"
                    />
                  </div>
                </div>
              </div>

              {/* Previous Reviews Section */}
              {selectedTaskToReview.review_history &&
                selectedTaskToReview.review_history.length > 0 && (
                  <div>
                    <h3 className="text-md mb-2 font-medium">
                      Previous Reviews
                    </h3>
                    <div className="max-h-40 overflow-y-auto rounded border border-gray-200 dark:border-gray-700">
                      {selectedTaskToReview.review_history.map(
                        (review, index) => (
                          <div
                            key={index}
                            className="border-b border-gray-200 p-3 last:border-b-0 dark:border-gray-700"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium">
                                {actorsList.find(
                                  (a) => a.id === review.reviewer_id,
                                )?.name || "Unknown"}
                              </span>
                              <span className="text-sm text-gray-500">
                                {new Date(review.reviewed_at).toLocaleString()}
                              </span>
                            </div>
                            <p className="mt-1 text-sm">{review.comment}</p>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsReviewTaskDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitReview}
              disabled={!reviewFormData.comment.trim()}
            >
              Submit Review
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reviews Dialog */}
      <Dialog open={isReviewsDialogOpen} onOpenChange={setIsReviewsDialogOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>Manage Reviews</DialogTitle>
          </DialogHeader>

          {selectedTaskForReviews && (
            <div className="grid gap-6 py-4">
              {/* Task Information Section */}
              <div className="rounded-md bg-gray-50 p-4 dark:bg-gray-800">
                <h3 className="mb-2 text-lg font-medium">
                  {selectedTaskForReviews.title}
                </h3>
                <div className="mb-2 text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Status:</span>{" "}
                  <Badge
                    variant={
                      selectedTaskForReviews.status === "completed"
                        ? "outline"
                        : "outline"
                    }
                  >
                    {selectedTaskForReviews.status}
                  </Badge>
                </div>
                <div className="mb-4 text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Description:</span>
                  <p className="mt-1 whitespace-pre-wrap rounded bg-white p-2 text-sm dark:bg-gray-700">
                    {selectedTaskForReviews.description}
                  </p>
                </div>

                {/* Task Result Preview */}
                {selectedTaskForReviews.result && (
                  <div className="mb-2">
                    <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                      Result:
                    </span>
                    <div className="relative mt-1">
                      <div className="absolute right-2 top-2 z-10">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            // Copy appropriate content based on type
                            const contentToCopy = hasMarkdownContent(
                              selectedTaskForReviews.result,
                            )
                              ? getMarkdownContent(
                                  selectedTaskForReviews.result,
                                )
                              : JSON.stringify(
                                  selectedTaskForReviews.result,
                                  null,
                                  2,
                                );

                            navigator.clipboard.writeText(contentToCopy);
                            // We don't have a state for this feedback, so we'll use a temporary visual cue
                            const btn =
                              document.activeElement as HTMLButtonElement;
                            if (btn) {
                              const originalText = btn.innerHTML;
                              btn.innerHTML =
                                '<span class="flex items-center"><svg class="mr-1 h-4 w-4 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>Copied!</span>';
                              setTimeout(() => {
                                btn.innerHTML = originalText;
                              }, 2000);
                            }
                          }}
                          title="Copy to clipboard"
                        >
                          <span className="flex items-center">
                            <ForwardedIconComponent
                              name="Copy"
                              className="mr-1 h-4 w-4"
                            />
                            Copy
                          </span>
                        </Button>
                      </div>

                      {hasMarkdownContent(selectedTaskForReviews.result) ? (
                        <div className="prose max-w-none overflow-x-auto rounded-md bg-white p-4 pt-12 dark:prose-invert dark:bg-gray-900">
                          <Markdown>
                            {getMarkdownContent(selectedTaskForReviews.result)}
                          </Markdown>
                        </div>
                      ) : (
                        <div className="overflow-x-auto rounded-md bg-gray-100 p-4 pt-12 font-mono text-xs dark:bg-gray-800">
                          {formatJSON(selectedTaskForReviews.result)}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Review List */}
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-md font-medium">
                    Reviews ({getAllReviews(selectedTaskForReviews).length})
                  </h3>
                </div>

                {/* Add Review Form */}
                <div className="mb-4 rounded-md border border-gray-200 p-4 dark:border-gray-700">
                  <div className="grid gap-4">
                    <div>
                      <Label htmlFor="new-comment" className="mb-2 block">
                        Add New Review
                      </Label>
                      <Textarea
                        id="new-comment"
                        value={reviewFormData.comment}
                        onChange={(e) =>
                          handleReviewFormChange("comment", e.target.value)
                        }
                        className="min-h-[100px] w-full"
                        placeholder="Provide feedback on this task. What needs to be improved or corrected?"
                      />
                    </div>
                    <div className="flex justify-end">
                      <Button
                        onClick={() => {
                          setSelectedTaskToReview(selectedTaskForReviews);
                          handleSubmitReview();
                        }}
                        disabled={!reviewFormData.comment.trim()}
                      >
                        Submit Review
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Reviews List */}
                {getAllReviews(selectedTaskForReviews).length === 0 ? (
                  <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-gray-300 p-6 text-center dark:border-gray-700">
                    <ForwardedIconComponent
                      name="MessageSquare"
                      className="mb-2 h-8 w-8 text-gray-400"
                    />
                    <p className="text-gray-500 dark:text-gray-400">
                      No reviews yet
                    </p>
                    <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                      Add the first review for this task using the form above
                    </p>
                  </div>
                ) : (
                  <div>
                    <h4 className="mb-2 text-sm font-medium text-gray-600 dark:text-gray-300">
                      Review History
                    </h4>
                    <div className="max-h-60 overflow-y-auto rounded border border-gray-200 dark:border-gray-700">
                      {getAllReviews(selectedTaskForReviews).map(
                        (review, index) => (
                          <div
                            key={index}
                            className="border-b border-gray-200 p-3 last:border-b-0 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <ForwardedIconComponent
                                  name="User"
                                  className="h-4 w-4 text-blue-600"
                                />
                                <span className="font-medium">
                                  {actorsList.find(
                                    (a) => a.id === review.reviewer_id,
                                  )?.name || "Unknown"}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-gray-500">
                                  {new Date(
                                    review.reviewed_at,
                                  ).toLocaleString()}
                                </span>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
                                  onClick={() => handleEditReview(index)}
                                  title="Edit review"
                                >
                                  <ForwardedIconComponent
                                    name="Pencil"
                                    className="h-3 w-3"
                                  />
                                </Button>
                              </div>
                            </div>
                            <p className="mt-2 whitespace-pre-wrap rounded bg-white p-2 text-sm dark:bg-gray-900">
                              {review.comment}
                            </p>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsReviewsDialogOpen(false);
              }}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Review Dialog */}
      <Dialog
        open={editingReviewIndex !== null}
        onOpenChange={(open) => {
          if (!open) setEditingReviewIndex(null);
        }}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Review</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div>
              <Label htmlFor="edit-comment" className="mb-2 block">
                Review Comments
              </Label>
              <Textarea
                id="edit-comment"
                value={editReviewFormData.comment}
                onChange={(e) =>
                  setEditReviewFormData({
                    ...editReviewFormData,
                    comment: e.target.value,
                  })
                }
                className="min-h-[120px] w-full"
                placeholder="Update your review comments"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditingReviewIndex(null)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveEditedReview}
              disabled={!editReviewFormData.comment.trim()}
            >
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
