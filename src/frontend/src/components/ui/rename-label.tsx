import { useEffect, useRef, useState } from "react";
import { cn } from "../../utils/utils";

export default function RenameLabel(props) {
  const [internalState, setInternalState] = useState(false);
  const [isRename, setIsRename] = props.rename
    ? [props.rename, props.setRename]
    : [internalState, setInternalState];

  useEffect(() => {
    if (props.value) setComponentValue(props.value);
  }, [props.value]);

  const [componentValue, setComponentValue] = useState(props.value);
  useEffect(() => {
    if (isRename) {
      setComponentValue(props.value);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          setIsRename(false);
          props.setValue("");
        }
      });
      if (inputRef.current) {
        setTimeout(() => {
          inputRef.current?.focus();
        }, 100);
      }
    }
    resizeInput();
    return () => {
      if (isRename) document.removeEventListener("keydown", () => {});
    };
  }, [isRename]);

  const inputRef = useRef<HTMLInputElement | null>(null);

  const resizeInput = () => {
    const input = inputRef.current;
    if (input) {
      const span = document.createElement("span");
      span.style.position = "absolute";
      span.style.visibility = "hidden";
      span.style.whiteSpace = "pre";
      span.style.font = window.getComputedStyle(input).font;
      span.textContent = input.value;

      document.body.appendChild(span);
      const textWidth = span.getBoundingClientRect().width;
      document.body.removeChild(span);

      input.style.width = `${textWidth + 16}px`;
    }
  };
  return (
    <div>
      {isRename ? (
        <input
          autoFocus
          ref={inputRef}
          onInput={resizeInput}
          className={cn(
            "nopan nodelete nodrag noflow rounded-md bg-transparent px-2 outline-ring hover:outline focus:border-none focus:outline active:outline",
            props.className,
          )}
          onBlur={() => {
            setIsRename(false);
            if (props.value !== "") {
              props.setValue(componentValue);
            }
          }}
          value={componentValue}
          onChange={(event) => {
            setComponentValue(event.target.value);
          }}
        />
      ) : (
        <div className="flex items-center gap-2">
          <span
            className={cn("truncate px-2 text-left", props.className)}
            onDoubleClick={() => {
              setIsRename(true);
              setComponentValue(props.value);
            }}
          >
            {props.value}
          </span>
        </div>
      )}
    </div>
  );
}
