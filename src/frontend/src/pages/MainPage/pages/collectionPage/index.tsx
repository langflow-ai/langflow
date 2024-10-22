import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useState } from "react";
import ModalsComponent from "../../components/modalsComponent";

const CollectionPage = () => {
  const [view, setView] = useState<"list" | "grid">("list");
  const [type, setType] = useState<"flows" | "components">("flows");
  const [newProjectModal, setNewProjectModal] = useState<boolean>(false);
  const navigate = useCustomNavigate();

  return (
    <div className="mx-5 w-full">
      {/* Title */}
      <div className="pb-8 pt-10 text-xl font-semibold">My Flows</div>
      <div className="flex pb-8">
        <Button
          unstyled
          onClick={() => setType("flows")}
          className={`border-b ${
            type === "flows"
              ? "border-b-2 border-white font-semibold text-white"
              : "text-zinc-500"
          } px-3 pb-1`}
        >
          Flows
        </Button>
        <Button
          unstyled
          className={`border-b ${
            type === "components"
              ? "border-b-2 border-white font-semibold text-white"
              : "text-zinc-500"
          } px-3 pb-1`}
          onClick={() => setType("components")}
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
          <div className="px-py flex rounded-lg border border-zinc-900 bg-zinc-900">
            <Button
              unstyled
              className={`rounded-lg border border-zinc-900 p-2 ${
                view === "list"
                  ? "bg-black text-white"
                  : "bg-zinc-900 text-zinc-500"
              }`}
              onClick={() => setView("list")}
            >
              <ForwardedIconComponent
                name="list"
                aria-hidden="true"
                className="h-5 w-5"
              />
            </Button>
            <Button
              unstyled
              className={`rounded-lg border border-zinc-900 p-2 ${
                view === "grid"
                  ? "bg-black text-white"
                  : "bg-zinc-900 text-zinc-500"
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
            className="border border-zinc-700 dark:bg-transparent dark:text-white"
            onClick={() => navigate("/store")}
          >
            <ForwardedIconComponent
              name="store"
              aria-hidden="true"
              className="h-4 w-4"
            />
            Browse Store
          </Button>
          <Button onClick={() => setNewProjectModal(true)}>
            <ForwardedIconComponent
              name="plus"
              aria-hidden="true"
              className="h-4 w-4"
            />
            New Flow
          </Button>
        </div>
      </div>

      {/* Flows */}
      {type === "flows" ? (
        <>
          {view === "grid" ? (
            <div className="mt-8 grid grid-cols-3 gap-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="my-1 flex flex-col rounded-lg border p-5"
                >
                  <div className="flex w-full items-center gap-2">
                    <div className="mr-3 flex rounded-lg border bg-red-500 p-3">
                      <ForwardedIconComponent
                        name="bell"
                        aria-hidden="true"
                        className="h-5 w-5 dark:text-black"
                      />
                    </div>
                    <div className="flex w-full items-center justify-between">
                      <div>
                        <div className="text-lg font-semibold">
                          Project Name
                        </div>
                        <div className="text-xs text-zinc-500">
                          Edited 2 days ago by{" "}
                          <span className="font-semibold">
                            deon.sanchez@datastax.com
                          </span>
                        </div>
                      </div>
                      <Button unstyled>
                        <ForwardedIconComponent
                          name="ellipsis"
                          aria-hidden="true"
                          className="mx-2 h-5 w-5"
                        />
                      </Button>
                    </div>
                  </div>

                  <div className="py-5 text-sm">
                    Automates data collection from multiple sources to
                    streamline data management.
                  </div>

                  <div className="flex justify-end">
                    <Button variant="outline">Playground</Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-8 flex h-full flex-col">
              {Array.from({ length: 3 }).map((_, index) => (
                <div className="my-1 flex justify-between rounded-lg border p-3">
                  {/* left side */}
                  <div className="flex items-center gap-2">
                    {/* Icon */}
                    <div className="item-center mr-3 flex justify-center rounded-lg border bg-red-500 p-3">
                      <ForwardedIconComponent
                        name="bell"
                        aria-hidden="true"
                        className="flex h-5 w-5 items-center justify-center dark:text-black"
                      />
                    </div>

                    <div className="flex flex-col justify-start">
                      <div className="flex items-baseline gap-2">
                        <div className="text-lg font-semibold">
                          Project Name
                        </div>
                        <div className="item-baseline text-xs text-zinc-500">
                          Edited 2 days ago by{" "}
                          <span className="font-semibold">
                            deon.sanchez@datastax.com
                          </span>
                        </div>
                      </div>
                      <div className="text-sm text-zinc-500">
                        Automates data collection from multiple sources to
                        streamline data management.
                      </div>
                    </div>
                  </div>

                  {/* right side */}
                  <div className="flex items-center gap-2">
                    <Button variant="outline">Playground</Button>
                    <Button unstyled>
                      <ForwardedIconComponent
                        name="ellipsis"
                        aria-hidden="true"
                        className="mx-2 h-5 w-5"
                      />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <></>
      )}
      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => {}}
        handleDeleteFolder={() => {}}
      />
    </div>
  );
};

export default CollectionPage;
