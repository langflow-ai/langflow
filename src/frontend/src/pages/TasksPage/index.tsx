import { useGetTasks } from "@/controllers/API/queries/tasks/use-get-tasks";
import { useEffect, useRef, useState } from "react";
import { columns } from "./components/columns";
import { DataTable } from "./components/data-table";
import { UserNav } from "./components/user-nav";
import { Task } from "./data/schema";

// Import the mock tasks data
import mockTasks from "./data/tasks.json";

export default function TaskPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const getTasks = useGetTasks();
  const tasksLoaded = useRef(false);

  useEffect(() => {
    const loadTasks = async () => {
      if (tasksLoaded.current) return; // Skip if tasks have already been loaded

      try {
        const result = await getTasks.mutateAsync({});
        setTasks(result);
      } catch (error) {
        console.error("Error fetching tasks:", error);
        // If the request fails, fall back to mock tasks
        setTasks(mockTasks);
      } finally {
        tasksLoaded.current = true; // Mark tasks as loaded
      }
    };

    loadTasks();
  }, [getTasks]);

  return (
    <div className="hidden h-full flex-1 flex-col space-y-8 p-8 md:flex">
      <div className="flex items-center justify-between space-y-2">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome back!</h2>
          <p className="text-muted-foreground">
            Here&apos;s a list of your tasks for this month!
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <UserNav />
        </div>
      </div>
      <DataTable data={tasks} columns={columns} />
    </div>
  );
}
