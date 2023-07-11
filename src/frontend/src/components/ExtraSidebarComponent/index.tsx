import { Disclosure } from "@headlessui/react";
import { useContext } from "react";
import { Link } from "react-router-dom";
import { locationContext } from "../../contexts/locationContext";
import { classNames } from "../../utils";

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
        className={` ${isStackedOpen ? "w-52" : "w-0 "} unused-side-bar-aside`}
      >
        <div className="unused-side-bar-arrangement">
          <div className="unused-side-bar-division">
            {extraNavigation.options ? (
              <div className="p-4">
                <nav className="unused-side-bar-nav">
                  {extraNavigation.options.map((item) =>
                    !item.children ? (
                      <div key={item.name}>
                        <Link
                          to={item.href}
                          className={classNames(
                            item.href.split("/")[2] === current[4]
                              ? "unused-side-bar-link-colors-true"
                              : "unused-side-bar-link-colors-false",
                            "unused-side-bar-link"
                          )}
                        >
                          <item.icon
                            className={classNames(
                              item.href.split("/")[2] === current[4]
                                ? "text-ring"
                                : "unused-side-bar-icon-false",
                              "unused-side-bar-icon"
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
                                  ? "unused-side-bar-link-colors-true"
                                  : "unused-side-bar-link-colors-false",
                                "unused-side-bar-disclosure"
                              )}
                            >
                              <item.icon
                                className="unused-side-bar-disclosure-icon"
                                aria-hidden="true"
                              />
                              <span className="flex-1">{item.name}</span>
                              <svg
                                className={classNames(
                                  open
                                    ? "unused-side-bar-svg-true"
                                    : "text-ring",
                                  "unused-side-bar-svg"
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
                                      ? "unused-side-bar-link-colors-true"
                                      : "unused-side-bar-link-colors-false",
                                    "unused-side-bar-disclosure-panel"
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
