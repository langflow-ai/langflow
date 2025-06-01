import { useEffect, useRef, useState } from "react";
import { cn } from "../../utils/utils";

export default function RenameLabel({
  value,
  setValue,
  className,
  rename,
  setRename,
}) {
  const [internalState, setInternalState] = useState(false);
  const [componentValue, setComponentValue] = useState(value);
  const [isRename, setIsRename] = rename
    ? [rename, setRename]
    : [internalState, setInternalState];

  useEffect(() => {
    if (value) setComponentValue(value);
  }, [value]);

  useEffect(() => {
    if (isRename) {
      setComponentValue(value);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          setIsRename(false);
          setValue("");
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

  const handleBlur = () => {
    setIsRename(false);
    if (componentValue !== "") {
      setValue(componentValue);
    }
  };

  const handleChange = (event) => {
    setComponentValue(event.target.value);
  };

  const handleDoubleClick = () => {
    setIsRename(true);
    setComponentValue(value);
  };

  const renderInput = () => (
    <input
      ref={inputRef}
      onInput={resizeInput}
      className={cn(
        "nopan nodelete nodrag noflow rounded-md bg-transparent px-2 outline-ring hover:outline focus:border-none focus:outline active:outline",
        className,
      )}
      onBlur={handleBlur}
      value={componentValue}
      onChange={handleChange}
    />
  );

  const renderSpan = () => (
    <div className="flex items-center gap-2">
      <span
        className={cn("truncate px-2 text-left", className)}
        onDoubleClick={handleDoubleClick}
      >
        {value}
      </span>
    </div>
  );

  return <div>{isRename ? renderInput() : renderSpan()}</div>;
}
