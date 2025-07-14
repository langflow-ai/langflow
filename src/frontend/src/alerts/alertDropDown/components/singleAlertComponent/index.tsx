import { CustomLink } from "@/customization/components/custom-link";
import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import IconComponent from "../../../../components/common/genericIconComponent";
import { SingleAlertComponentType } from "../../../../types/alerts";

export default function SingleAlert({
  dropItem,
  removeAlert,
}: SingleAlertComponentType): JSX.Element {
  const [show, setShow] = useState(true);
  const type = dropItem.type;

  return type === "error" ? (
    <div
      className="bg-error-background mx-2 mb-2 flex rounded-md p-3"
      key={dropItem.id}
    >
      <div className="shrink-0">
        <IconComponent name="XCircle" className="text-status-red h-5 w-5" />
      </div>
      <div className="ml-3">
        <h3 className="text-error-foreground word-break-break-word text-sm font-medium">
          {dropItem.title}
        </h3>
        {dropItem.list ? (
          <div className="text-error-foreground mt-2 text-sm">
            <ul className="list-disc space-y-1 pl-5 align-top">
              {dropItem.list.map((item, idx) => (
                <li className="word-break-break-word" key={idx}>
                  <Markdown
                    linkTarget="_blank"
                    remarkPlugins={[remarkGfm]}
                    className="align-text-top"
                    components={{
                      a: ({ node, ...props }) => (
                        <a
                          href={props.href}
                          target="_blank"
                          className="underline"
                          rel="noopener noreferrer"
                        >
                          {props.children}
                        </a>
                      ),
                      p({ node, ...props }) {
                        return (
                          <span className="inline-block w-fit max-w-full align-text-top">
                            {props.children}
                          </span>
                        );
                      },
                    }}
                  >
                    {Array.isArray(item) ? item.join("\n") : item}
                  </Markdown>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <></>
        )}
      </div>
      <div className="ml-auto pl-3">
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={() => {
              setShow(false);
              setTimeout(() => {
                removeAlert(dropItem.id);
              }, 500);
            }}
            className="text-status-red inline-flex rounded-md p-1.5"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent name="X" className="text-error-foreground h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  ) : type === "notice" ? (
    <div
      className="bg-info-background mx-2 mb-2 flex rounded-md p-3"
      key={dropItem.id}
    >
      <div className="shrink-0 cursor-help">
        <IconComponent name="Info" className="text-status-blue h-5 w-5" />
      </div>
      <div className="ml-3 flex-1 md:flex md:justify-between">
        <p className="text-info-foreground text-sm font-medium">
          {dropItem.title}
        </p>
        <p className="mt-3 text-sm md:mt-0 md:ml-6">
          {dropItem.link ? (
            <CustomLink
              to={dropItem.link}
              className="text-info-foreground hover:text-accent-foreground font-medium whitespace-nowrap"
            >
              Details
            </CustomLink>
          ) : (
            <></>
          )}
        </p>
      </div>
      <div className="ml-auto pl-3">
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={() => {
              setShow(false);
              setTimeout(() => {
                removeAlert(dropItem.id);
              }, 500);
            }}
            className="text-info-foreground inline-flex rounded-md p-1.5"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent name="X" className="text-info-foreground h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  ) : (
    <div
      className="bg-success-background mx-2 mb-2 flex rounded-md p-3"
      key={dropItem.id}
    >
      <div className="shrink-0">
        <IconComponent
          name="CheckCircle2"
          className="text-status-green h-5 w-5"
        />
      </div>
      <div className="ml-3">
        <p className="text-success-foreground text-sm font-medium">
          {dropItem.title}
        </p>
      </div>
      <div className="ml-auto pl-3">
        <div className="-mx-1.5 -my-1.5">
          <button
            type="button"
            onClick={() => {
              setShow(false);
              setTimeout(() => {
                removeAlert(dropItem.id);
              }, 500);
            }}
            className="text-status-green inline-flex rounded-md p-1.5"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent
              name="X"
              className="text-success-foreground h-4 w-4"
            />
          </button>
        </div>
      </div>
    </div>
  );
}
