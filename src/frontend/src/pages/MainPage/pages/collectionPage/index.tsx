import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const CollectionPage = () => {
  return (
    <div className="mx-5 w-full">
      <div className="pb-8 pt-10 text-xl font-semibold">My Projects</div>
      <div className="flex pb-8">
        <Button
          unstyled
          className="border-b-2 border-white px-3 pb-1 font-semibold"
        >
          Projects
        </Button>
        <Button
          unstyled
          className="border-b border-zinc-700 px-3 pb-1 text-zinc-500"
        >
          Components
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex justify-between">
        <div className="flex w-4/12">
          <Input type="search" placeholder="Search flows..." className="mr-3" />
          <div className="px-py flex rounded-lg border bg-zinc-900">
            <Button unstyled className="rounded-lg border bg-black p-2">
              <ForwardedIconComponent
                name="list"
                aria-hidden="true"
                className="h-5 w-5 text-white"
              />
            </Button>
            <Button unstyled className="p-2">
              <ForwardedIconComponent
                name="layout-grid"
                aria-hidden="true"
                className="h-5 w-5 text-zinc-500"
              />
            </Button>
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="outline">
            <ForwardedIconComponent
              name="store"
              aria-hidden="true"
              className="h-4 w-4"
            />
            Browse Store
          </Button>
          <Button>
            <ForwardedIconComponent
              name="plus"
              aria-hidden="true"
              className="h-4 w-4"
            />
            New Project
          </Button>
        </div>
      </div>

      {/* Projects list */}
      {true ? (
        <div className="mt-8 grid grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div className="my-1 flex rounded-lg border p-3">
              {/* left side */}
              <div className="flex items-center gap-2">
                {/* Icon */}
                <div className="mr-3 flex rounded-lg border bg-red-500 p-3">
                  <ForwardedIconComponent
                    name="bell"
                    aria-hidden="true"
                    className="flex h-5 w-5 items-center justify-center dark:text-black"
                  />
                </div>
                <div>
                  <div>
                    <div className="text-lg font-semibold">Project Name</div>
                    <div className="item-baseline text-xs text-zinc-500">
                      Edited 2 days ago by{" "}
                      <span className="font-semibold">
                        deon.sanchez@datastax.com
                      </span>
                    </div>
                  </div>
                </div>

                {/* <div className="flex">
                  <div className="flex items-baseline gap-2">
                    <div className="text-lg font-semibold">Project Name</div>
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
                </div> */}
              </div>

              {/* right side */}
              {/* <div className="flex items-center gap-2">
                <Button variant="outline">Playground</Button>
                <Button unstyled>
                  <ForwardedIconComponent
                    name="ellipsis"
                    aria-hidden="true"
                    className="mx-2 h-5 w-5"
                  />
                </Button>
              </div> */}
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
                    <div className="text-lg font-semibold">Project Name</div>
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
    </div>
  );
};

export default CollectionPage;
