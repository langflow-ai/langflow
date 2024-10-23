import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

interface HeaderComponentProps {
  flowType: "flows" | "components";
  setFlowType: (flowType: "flows" | "components") => void;
  view: "list" | "grid";
  setView: (view: "list" | "grid") => void;
  setNewProjectModal: (newProjectModal: boolean) => void;
}

const HeaderComponent = ({
  flowType,
  setFlowType,
  view,
  setView,
  setNewProjectModal,
}: HeaderComponentProps) => {
  const navigate = useCustomNavigate();

  return (
    <>
      <div className="pb-8 pt-10 text-xl font-semibold">My Flows</div>
      <div className="flex pb-8">
        <Button
          unstyled
          onClick={() => setFlowType("flows")}
          className={`border-b ${
            flowType === "flows"
              ? "border-b-2 border-black font-semibold dark:border-white dark:text-white"
              : "text-zinc-500"
          } px-3 pb-1`}
        >
          Flows
        </Button>
        <Button
          unstyled
          className={`border-b ${
            flowType === "components"
              ? "border-b-2 border-black font-semibold dark:border-white dark:text-white"
              : "text-zinc-500"
          } px-3 pb-1`}
          onClick={() => setFlowType("components")}
        >
          Components
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex justify-between">
        <div className="flex w-4/12">
          <Input
            icon="search"
            type="search"
            placeholder="Search flows..."
            className="mr-2"
          />
          <div className="px-py flex rounded-lg border border-zinc-300 bg-zinc-300 dark:border-zinc-900 dark:bg-zinc-900">
            <Button
              unstyled
              className={`rounded-lg border border-zinc-900 p-2 ${
                view === "list"
                  ? "border-zinc-300 bg-white text-black shadow-md dark:border-zinc-900 dark:bg-black dark:text-white"
                  : "border-zinc-300 bg-zinc-300 text-zinc-500 dark:border-zinc-900 dark:bg-black dark:bg-zinc-900"
              }`}
              onClick={() => setView("list")}
            >
              <ForwardedIconComponent
                name="menu"
                aria-hidden="true"
                className="h-5 w-5"
              />
            </Button>
            <Button
              unstyled
              className={`rounded-lg border border-zinc-900 p-2 ${
                view === "grid"
                  ? "border-zinc-300 bg-white text-black shadow-md dark:border-zinc-900 dark:bg-black dark:text-white"
                  : "border-zinc-300 bg-zinc-300 text-zinc-500 dark:border-zinc-900 dark:bg-black dark:bg-zinc-900"
              }`}
              onClick={() => setView("grid")}
            >
              <ForwardedIconComponent
                name="layout-grid"
                aria-hidden="true"
                className="h-5 w-5"
              />
            </Button>
          </div>
        </div>
        <div className="flex gap-3">
          <Button
            className="border border-zinc-200 bg-white text-[black] hover:border-zinc-400 hover:bg-white hover:shadow-sm dark:border-zinc-600 dark:bg-transparent dark:text-white dark:hover:border-white"
            onClick={() => navigate("/store")}
          >
            <ForwardedIconComponent
              name="store"
              aria-hidden="true"
              className="h-4 w-4"
            />
            Browse Store
          </Button>
          <Button
            onClick={() => setNewProjectModal(true)}
            className="text-white dark:bg-white dark:text-[black]"
          >
            <ForwardedIconComponent
              name="plus"
              aria-hidden="true"
              className="h-4 w-4 text-[white] dark:text-[black]"
            />
            New Flow
          </Button>
        </div>
      </div>
    </>
  );
};

export default HeaderComponent;
