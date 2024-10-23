import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import useTheme from "@/customization/hooks/use-custom-theme";
import { useEffect, useState } from "react";

export const ThemeButtons = () => {
  const { systemTheme, dark, setThemePreference } = useTheme();
  const [selectedTheme, setSelectedTheme] = useState(
    systemTheme ? "system" : dark ? "dark" : "light",
  );
  const [hasInteracted, setHasInteracted] = useState(false); // Track user interaction

  useEffect(() => {
    if (!hasInteracted) {
      // Set initial theme without triggering the animation
      if (systemTheme) {
        setSelectedTheme("system");
      } else if (dark) {
        setSelectedTheme("dark");
      } else {
        setSelectedTheme("light");
      }
    }
  }, [systemTheme, dark, hasInteracted]);

  const handleThemeChange = (theme) => {
    setHasInteracted(true); // Mark that a button has been clicked
    setSelectedTheme(theme);
    setThemePreference(theme);
  };

  return (
    <div className="relative ml-auto inline-flex rounded-full border border-zinc-200 p-0.5 dark:border-zinc-700">
      {/* Sliding Indicator - Behind the Buttons */}
      <div
        className={`absolute bottom-0.5 left-[1px] top-0.5 w-[30%] rounded-full bg-amber-400 ${
          hasInteracted ? "transition-all duration-300" : ""
        } dark:bg-purple-400`}
        style={{
          transform: `translateX(${
            selectedTheme === "light"
              ? "2%"
              : selectedTheme === "dark"
                ? "112%"
                : "223%"
          })`,
          zIndex: 0, // Ensure it's behind the buttons
        }}
      ></div>

      {/* Light Theme Button */}
      <Button
        unstyled
        className={`relative z-10 inline-flex items-center rounded-full px-1 ${
          selectedTheme === "light"
            ? "text-black dark:text-[black]"
            : "hover:text-black dark:text-[white] dark:hover:bg-amber-400 dark:hover:text-[black]"
        }`}
        onClick={() => handleThemeChange("light")}
      >
        <ForwardedIconComponent name="sun" className="w-4" />
      </Button>

      {/* Dark Theme Button */}
      <Button
        unstyled
        className={`relative z-10 mx-1 inline-flex items-center rounded-full px-1 ${
          selectedTheme === "dark"
            ? "text-black dark:text-[black] dark:hover:bg-purple-400 dark:hover:text-[black]"
            : "hover:bg-purple-400 hover:text-[black] hover:text-[white] dark:hover:text-[black]"
        }`}
        onClick={() => handleThemeChange("dark")}
      >
        <ForwardedIconComponent name="moon" className="w-4" />
      </Button>

      {/* System Theme Button */}
      <Button
        unstyled
        className={`relative z-10 inline-flex items-center rounded-full px-1 ${
          selectedTheme === "system"
            ? "text-black dark:bg-[white] dark:text-[black]"
            : "hover:bg-[black] hover:text-[white] dark:hover:bg-[white] dark:hover:text-[black]"
        }`}
        onClick={() => handleThemeChange("system")}
      >
        <ForwardedIconComponent name="monitor" className="w-4" />
      </Button>
    </div>
  );
};

export default ThemeButtons;
