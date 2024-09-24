import IconComponent from "@/components/genericIconComponent";
import LoadingComponent from "@/components/loadingComponent";
import PageLayout from "@/components/pageLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDeleteTask } from "@/controllers/API/queries/tasks/use-delete-task";
import { useGetTasks } from "@/controllers/API/queries/tasks/use-get-tasks";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { Task } from "@/types/Task";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
import TableComponent from "../../components/tableComponent";
import AddNewTaskButton from "./components/AddNewTaskButton";

const POLLING_INTERVAL = 5000; // 5 seconds

export default function TaskPage() {
  const [inputValue, setInputValue] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [taskData, setTaskData] = useState<Task[]>([]);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();
  const queryClient = useQueryClient();

  const {
    data: tasks,
    isLoading,
    error,
    refetch,
  } = useGetTasks({
    refetchInterval: POLLING_INTERVAL,
  });
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
            queryClient.invalidateQueries({ queryKey: ["tasks"] });
          },
        },
      );
    });
  }

  const isFetchingTasks = !!useIsFetching({
    queryKey: ["tasks"],
    exact: false,
  });

  if (error) {
    return <div>Error loading tasks: {(error as Error).message}</div>;
  }

  return (
    <>
      <PageLayout
        title="Tasks"
        description="Manage and track your tasks efficiently."
        button={
          <div className="flex gap-2">
            <AddNewTaskButton asChild>
              <Button variant="primary">
                <IconComponent name="Plus" className="w-4" />
                Add New Task
              </Button>
            </AddNewTaskButton>
          </div>
        }
      >
        <div className="flex h-full w-full flex-col space-y-8 pb-8">
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
      </PageLayout>
    </>
  );
}
