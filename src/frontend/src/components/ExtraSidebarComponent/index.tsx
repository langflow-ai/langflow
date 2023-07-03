import { Disclosure } from "@headlessui/react";
import { useContext, useState } from "react";
import { Link } from "react-router-dom";
import { classNames } from "../../utils";
import { locationContext } from "../../contexts/locationContext";

export default function ExtraSidebar() {
  const {
    current,
    isStackedOpen,
    setIsStackedOpen,
    extraNavigation,
    extraComponent,
  } = useContext(locationContext);

  return (
    <>
      <aside
        className={` ${
          isStackedOpen ? "w-52" : "w-0 "
        } flex flex-shrink-0 flex-col overflow-hidden border-r  transition-all duration-500`}
      >
        <div className="flex h-full  w-52 flex-col items-start overflow-y-auto border bg-background scrollbar-hide">
          <div className="flex w-full flex-grow flex-col">
            {extraNavigation.options ? (
              <div className="p-4">
                <nav className="flex-1 space-y-1">
                  {extraNavigation.options.map((item) =>
                    !item.children ? (
                      <div key={item.name}>
                        <Link
                          to={item.href}
                          className={classNames(
                            item.href.split("/")[2] === current[4]
                              ? "bg-muted text-foreground"
                              : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
                            "group flex w-full items-center rounded-md py-2 pl-2 text-sm font-medium"
                          )}
                        >
                          <item.icon
                            className={classNames(
                              item.href.split("/")[2] === current[4]
                                ? "text-ring"
                                : "text-ring group-hover:text-accent-foreground",
                              "mr-3 flex-shrink-0 h-6 w-6"
                            )}
                          />
                          {item.name}
                        </Link>
                      </div>
                    ) : (
                      <Disclosure
                        as="div"
                        key={item.name}
                        className="space-y-1"
                      >
                        {({ open }) => (
                          <>
                            <Disclosure.Button
                              className={classNames(
                                item.href.split("/")[2] === current[4]
                                  ? "bg-muted text-foreground"
                                  : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
                                "group flex w-full items-center rounded-md py-2 pl-2 pr-1 text-left text-sm font-medium focus:outline-none focus:ring-1 focus:ring-ring"
                              )}
                            >
                              <item.icon
                                className="mr-3 h-6 w-6 flex-shrink-0 text-ring group-hover:text-accent-foreground"
                                aria-hidden="true"
                              />
                              <span className="flex-1">{item.name}</span>
                              <svg
                                className={classNames(
                                  open ? "text-ring rotate-90" : "text-ring",
                                  "ml-3 h-5 w-5 flex-shrink-0 transition-rotate duration-150 ease-in-out group-hover:text-accent-foreground"
                                )}
                                viewBox="0 0 20 20"
                                aria-hidden="true"
                              >
                                <path
                                  d="M6 6L14 10L6 14V6Z"
                                  fill="currentColor"
                                />
                              </svg>
                            </Disclosure.Button>
                            <Disclosure.Panel className="space-y-1">
                              {item.children.map((subItem) => (
                                <Link
                                  key={subItem.name}
                                  to={subItem.href}
                                  className={classNames(
                                    subItem.href.split("/")[3] === current[5]
                                      ? "bg-muted text-foreground"
                                      : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
                                    "group flex w-full items-center rounded-md py-2 pl-11 pr-2 text-sm font-medium"
                                  )}
                                >
                                  {subItem.name}
                                </Link>
                              ))}
                            </Disclosure.Panel>
                          </>
                        )}
                      </Disclosure>
                    )
                  )}
                </nav>
              </div>
            ) : (
              extraComponent
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
