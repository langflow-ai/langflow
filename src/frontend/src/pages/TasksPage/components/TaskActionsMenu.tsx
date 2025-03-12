import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  ContextMenuContent,
  ContextMenuItem,
} from "@/components/ui/context-menu";

import { useDeleteTask } from "@/controllers/API/queries/tasks/use-delete-task";
import { useGetTasks } from "@/controllers/API/queries/tasks/use-get-tasks";
import useAlertStore from "@/stores/alertStore";
import { useQueryClient } from "@tanstack/react-query";

interface TaskActionsMenuProps {
  taskId: string | null;
  onClose: () => void;
  onEdit?: (taskId: string) => void;
  onReview?: (taskId: string) => void;
}

export default function TaskActionsMenu({
  taskId,
  onClose,
  onEdit,
  onReview,
}: TaskActionsMenuProps) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: deleteTask } = useDeleteTask();
  const queryClient = useQueryClient();
  const { data: tasks } = useGetTasks();

  // Find the current task to check its status
  const currentTask = tasks?.find((task) => task.id === taskId);

  const handleDeleteTask = () => {
    if (!taskId) return;

    deleteTask(
      { taskId },
      {
        onSuccess: () => {
          setSuccessData({
            title: "Task deleted successfully",
          });
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          onClose();
        },
        onError: (error: any) => {
          setErrorData({
            title: "Error deleting task",
            list: [
              error?.response?.data?.detail ||
                "An unexpected error occurred while deleting the task.",
            ],
          });
        },
      },
    );
  };

  const handleEditTask = () => {
    if (taskId && onEdit) {
      onEdit(taskId);
      onClose();
    }
  };

  const handleReviewTask = () => {
    if (taskId && onReview) {
      onReview(taskId);
      onClose();
    }
  };

  // If no taskId, don't render the menu
  if (!taskId) return null;

  return (
    <ContextMenuContent className="w-40">
      <ContextMenuItem
        className="flex cursor-pointer items-center gap-2"
        onClick={handleEditTask}
      >
        <ForwardedIconComponent
          name="Pencil"
          className="h-4 w-4"
          aria-hidden="true"
        />
        <span>Edit</span>
      </ContextMenuItem>

      {currentTask?.status === "completed" && onReview && (
        <ContextMenuItem
          className="flex cursor-pointer items-center gap-2"
          onClick={handleReviewTask}
        >
          <ForwardedIconComponent
            name="CheckCheck"
            className="h-4 w-4"
            aria-hidden="true"
          />
          <span>Review</span>
        </ContextMenuItem>
      )}

      <ContextMenuItem
        className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
        onClick={handleDeleteTask}
      >
        <ForwardedIconComponent
          name="Trash2"
          className="h-4 w-4"
          aria-hidden="true"
        />
        <span>Delete</span>
      </ContextMenuItem>
    </ContextMenuContent>
  );
}
