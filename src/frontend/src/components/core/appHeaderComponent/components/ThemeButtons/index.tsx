import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useTheme from "@/customization/hooks/use-custom-theme";
import { useEffect, useState } from "react";

export const ThemeButtons = () => {
  const { systemTheme, dark, setThemePreference } = useTheme();
  const [selectedTheme, setSelectedTheme] = useState(
    systemTheme ? "system" : dark ? "dark" : "light",
  );
  const [hasInteracted, setHasInteracted] = useState(false);

  useEffect(() => {
    if (!hasInteracted) {
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
    setHasInteracted(true);
    setSelectedTheme(theme);
    setThemePreference(theme);
  };

  return (
    <div className="relative ml-auto inline-flex rounded-full border border-border/50 p-0.5 shadow-inner transition-colors duration-300 hover:border-border">
      {/* Sliding Indicator */}
      <div
        className={`absolute bottom-0.5 left-[1px] top-0.5 w-[30%] rounded-full backdrop-blur-sm ${
          hasInteracted ? "transition-all duration-300 ease-spring" : ""
        } ${
          selectedTheme === "light"
            ? "bg-amber-400/90"
            : selectedTheme === "dark"
            ? "bg-purple-500/90"
            : "bg-foreground/20"
        }`}
        style={{
          transform: `translateX(${
            selectedTheme === "light"
              ? "2%"
              : selectedTheme === "dark"
              ? "112%"
              : "223%"
          })`,
          zIndex: 0,
        }}
      />

      {/* Light Theme Button */}
      <Button
        unstyled
        className={`relative z-10 inline-flex items-center justify-center rounded-full p-1.5 transition-all duration-200 ${
          selectedTheme === "light"
            ? "text-amber-950 dark:text-amber-100"
            : "text-foreground/70 hover:text-foreground"
        }`}
        onClick={() => handleThemeChange("light")}
        data-testid="menu_light_button"
        id="menu_light_button"
      >
        <ForwardedIconComponent 
          strokeWidth={2} 
          name="Sun" 
          className={`h-3.5 w-3.5 transition-transform duration-200 ${
            selectedTheme === "light" ? "scale-110" : "scale-90"
          }`}
        />
      </Button>

      {/* Dark Theme Button */}
      <Button
        unstyled
        className={`relative z-10 mx-1 inline-flex items-center justify-center rounded-full p-1.5 transition-all duration-200 ${
          selectedTheme === "dark"
            ? "text-purple-100 dark:text-purple-100"
            : "text-foreground/70 hover:text-foreground"
        }`}
        onClick={() => handleThemeChange("dark")}
        data-testid="menu_dark_button"
        id="menu_dark_button"
      >
        <ForwardedIconComponent 
          strokeWidth={2} 
          name="Moon" 
          className={`h-3.5 w-3.5 transition-transform duration-200 ${
            selectedTheme === "dark" ? "scale-110" : "scale-90"
          }`}
        />
      </Button>

      {/* System Theme Button */}
      <Button
        unstyled
        className={`relative z-10 inline-flex items-center justify-center rounded-full p-1.5 transition-all duration-200 ${
          selectedTheme === "system"
            ? "text-background dark:text-background"
            : "text-foreground/70 hover:text-foreground"
        }`}
        onClick={() => handleThemeChange("system")}
        data-testid="menu_system_button"
        id="menu_system_button"
      >
        <ForwardedIconComponent
          name="Monitor"
          className={`h-3.5 w-3.5 transition-transform duration-200 ${
            selectedTheme === "system" ? "scale-110" : "scale-90"
          }`}
          strokeWidth={2}
        />
      </Button>
    </div>
  );
};

export default ThemeButtons;
