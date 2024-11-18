import { CustomLink } from "@/customization/components/custom-link";
import { useState } from "react";
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
      className="mx-2 mb-2 flex rounded-md bg-error-background p-3"
      key={dropItem.id}
    >
      <div className="flex-shrink-0">
        <IconComponent
          name="XCircle"
          className="h-5 w-5 text-status-red"
          aria-hidden="true"
        />
      </div>
      <div className="ml-3">
        <h3 className="text-sm font-medium text-error-foreground word-break-break-word">
          {dropItem.title}
        </h3>
        {dropItem.list ? (
          <div className="mt-2 text-sm text-error-foreground">
            <ul className="list-disc space-y-1 pl-5">
              {dropItem.list.map((item, idx) => (
                <li className="word-break-break-word" key={idx}>
                  {item}
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
            className="inline-flex rounded-md p-1.5 text-status-red"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent
              name="X"
              className="h-4 w-4 text-error-foreground"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </div>
  ) : type === "notice" ? (
    <div
      className="mx-2 mb-2 flex rounded-md bg-info-background p-3"
      key={dropItem.id}
    >
      <div className="flex-shrink-0 cursor-help">
        <IconComponent
          name="Info"
          className="h-5 w-5 text-status-blue"
          aria-hidden="true"
        />
      </div>
      <div className="ml-3 flex-1 md:flex md:justify-between">
        <p className="text-sm font-medium text-info-foreground">
          {dropItem.title}
        </p>
        <p className="mt-3 text-sm md:ml-6 md:mt-0">
          {dropItem.link ? (
            <CustomLink
              to={dropItem.link}
              className="whitespace-nowrap font-medium text-info-foreground hover:text-accent-foreground"
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
            className="inline-flex rounded-md p-1.5 text-info-foreground"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent
              name="X"
              className="h-4 w-4 text-info-foreground"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </div>
  ) : (
    <div
      className="mx-2 mb-2 flex rounded-md bg-success-background p-3"
      key={dropItem.id}
    >
      <div className="flex-shrink-0">
        <IconComponent
          name="CheckCircle2"
          className="h-5 w-5 text-status-green"
          aria-hidden="true"
        />
      </div>
      <div className="ml-3">
        <p className="text-sm font-medium text-success-foreground">
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
            className="inline-flex rounded-md p-1.5 text-status-green"
          >
            <span className="sr-only">Dismiss</span>
            <IconComponent
              name="X"
              className="h-4 w-4 text-success-foreground"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </div>
  );
}
