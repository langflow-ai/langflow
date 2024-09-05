import { useDeleteTask, useGetTasks } from "@/controllers/API/queries/tasks";
import { Task } from "@/types/Task";
import { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import LoadingComponent from "../../components/loadingComponent";
import TableComponent from "../../components/tableComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import useAlertStore from "../../stores/alertStore";
import AddNewTaskButton from "./components/AddNewTaskButton";

export default function TaskPage() {
  const [inputValue, setInputValue] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [taskData, setTaskData] = useState<Task[]>([]);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: tasks, isLoading, error, refetch } = useGetTasks();
  const { mutate: mutateDeleteTask } = useDeleteTask();

  useEffect(() => {
    if (tasks && Array.isArray(tasks)) {
      setTaskData(tasks);
    }
  }, [tasks]);

  const BadgeRenderer = (props: { value: string }) => {
    return props.value ? (
      <Badge variant="outline" size="sm">
        {props.value}
      </Badge>
    ) : null;
  };

  const DateRenderer = (props: { value: string }) => {
    return props.value ? new Date(props.value).toLocaleString() : "";
  };

  const colDefs: ColDef[] = [
    { headerName: "ID", field: "id", flex: 1 },
    { headerName: "Title", field: "title", flex: 2 },
    { headerName: "Description", field: "description", flex: 3 },
    {
      headerName: "Category",
      field: "category",
      flex: 1,
      cellRenderer: BadgeRenderer,
    },
    {
      headerName: "State",
      field: "state",
      flex: 1,
      cellRenderer: BadgeRenderer,
    },
    {
      headerName: "Status",
      field: "status",
      flex: 1,
      cellRenderer: BadgeRenderer,
    },
    {
      headerName: "Created At",
      field: "created_at",
      flex: 1,
      cellRenderer: DateRenderer,
    },
    {
      headerName: "Updated At",
      field: "updated_at",
      flex: 1,
      cellRenderer: DateRenderer,
    },
  ];

  function handleFilterTasks(input: string) {
    setInputValue(input);
    // Filtering is now handled by the TableComponent
  }

  async function removeTasks() {
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
            refetch(); // Refetch tasks after successful deletion
          },
        },
      );
    });
  }

  if (error) {
    return <div>Error loading tasks: {(error as Error).message}</div>;
  }

  return (
    <div className="task-page-panel flex h-full w-full flex-col pb-8">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <IconComponent name="SquareCheckBig" className="w-6" />
          Tasks
        </span>
      </div>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="text-lg font-semibold tracking-tight">
            Task Management
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage and track your tasks efficiently.
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <AddNewTaskButton asChild>
            <Button variant="primary">
              <IconComponent name="Plus" className="w-4" />
              Add New Task
            </Button>
          </AddNewTaskButton>
        </div>
      </div>
      <div className="flex w-full justify-between px-4 py-4">
        <div className="flex w-96 items-center gap-4">
          <Input
            placeholder="Search Tasks"
            value={inputValue}
            onChange={(e) => handleFilterTasks(e.target.value)}
          />
          {inputValue && (
            <IconComponent
              name="X"
              className="cursor-pointer"
              onClick={() => handleFilterTasks("")}
            />
          )}
        </div>
      </div>
      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <LoadingComponent remSize={12} />
        </div>
      ) : (
        <div className="flex h-full w-full flex-col justify-between">
          <TableComponent
            key="tasks"
            rowData={taskData}
            columnDefs={colDefs}
            onSelectionChanged={(event: any) => {
              setSelectedRows(
                event.api.getSelectedRows().map((row: Task) => row.id),
              );
            }}
            rowSelection="multiple"
            pagination={true}
            onDelete={removeTasks}
            quickFilterText={inputValue}
          />
        </div>
      )}
    </div>
  );
}
