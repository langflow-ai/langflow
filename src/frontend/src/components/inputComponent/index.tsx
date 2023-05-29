import { useContext, useEffect, useState } from "react";
import { InputComponentType } from "../../types/components";
import { classNames } from "../../utils";
import { TabsContext } from "../../contexts/tabsContext";

export default function InputComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  password,
}: InputComponentType) {
  const [myValue, setMyValue] = useState(value ?? "");
  const [pwdVisible, setPwdVisible] = useState(false);
  const { setDisableCopyPaste } = useContext(TabsContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);
  return (
    <div
      className={
        disabled
          ? "relative pointer-events-none cursor-not-allowed"
          : "relative"
      }
    >
      <input
        value={myValue}
        onFocus={() => {
          if (disableCopyPaste) setDisableCopyPaste(true);
        }}
        onBlur={() => {
          if (disableCopyPaste) setDisableCopyPaste(false);
        }}
        className={classNames(
          "block w-full pr-12 form-input dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
          disabled ? " bg-gray-200 dark:bg-gray-700" : "",
          password && !pwdVisible && myValue !== "" ? "password" : ""
        )}
        placeholder="Type something..."
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
      />
      <button
        className="absolute inset-y-0 right-0 items-center px-4 text-gray-600"
        onClick={() => {
          setPwdVisible(!pwdVisible);
        }}
      >
        {password &&
          (pwdVisible ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
              />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          ))}
      </button>
    </div>
  );
}
