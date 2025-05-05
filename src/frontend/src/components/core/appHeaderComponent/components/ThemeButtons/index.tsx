import ForwardedIconComponent from "@/components/common/genericIconComponent";
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
    <div className="relative ml-auto inline-flex rounded-full border border-border">
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
            ? "text-foreground"
            : "text-foreground hover:bg-amber-400 hover:text-background"
        }`}
        onClick={() => handleThemeChange("light")}
        data-testid="menu_light_button"
        id="menu_light_button"
      >
        <ForwardedIconComponent strokeWidth={2} name="Sun" className="w-4" />
      </Button>

      {/* Dark Theme Button */}
      <Button
        unstyled
        className={`relative z-10 mx-1 inline-flex items-center rounded-full px-1 ${
          selectedTheme === "dark"
            ? "bg-indigo-foreground text-primary hover:bg-indigo-foreground"
            : "text-foreground hover:bg-indigo-foreground hover:text-background"
        }`}
        onClick={() => handleThemeChange("dark")}
        data-testid="menu_dark_button"
        id="menu_dark_button"
      >
        <ForwardedIconComponent strokeWidth={2} name="Moon" className="w-4" />
      </Button>

      {/* System Theme Button */}
      <Button
        unstyled
        className={`relative z-10 inline-flex items-center rounded-full px-1 ${
          selectedTheme === "system"
            ? "bg-foreground text-background"
            : "hover:bg-foreground hover:text-background"
        }`}
        onClick={() => handleThemeChange("system")}
        data-testid="menu_system_button"
        id="menu_system_button"
      >
        <ForwardedIconComponent
          name="Monitor"
          className="w-4"
          strokeWidth={2}
        />
      </Button>
    </div>
  );
};

export default ThemeButtons;
