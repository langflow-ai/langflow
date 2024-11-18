import { useEffect, useRef, useState } from "react";

export default function HorizontalScrollFadeComponent({
  children,
  isFolder = true,
}: {
  children: JSX.Element | JSX.Element[];
  isFolder?: boolean;
}) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fadeContainerRef = useRef<HTMLDivElement>(null);
  const [divWidth, setDivWidth] = useState<number>(0);

  useEffect(() => {
    const handleResize = () => {
      if (scrollContainerRef.current) {
        setDivWidth(scrollContainerRef.current.clientWidth);
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize(); // call the function at start to get the initial width
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      if (!scrollContainerRef.current || !fadeContainerRef.current) return;

      const { scrollLeft, scrollWidth, clientWidth } =
        scrollContainerRef.current;
      const atStart = scrollLeft === 0;
      const atEnd = scrollLeft === scrollWidth - clientWidth;
      const isScrollable = scrollWidth > clientWidth;

      fadeContainerRef.current.classList.toggle(
        "fade-left",
        isScrollable && !atStart,
      );
      fadeContainerRef.current.classList.toggle(
        "fade-right",
        isScrollable && !atEnd,
      );
    };

    const scrollContainer = scrollContainerRef.current;
    if (scrollContainer) {
      scrollContainer.addEventListener("scroll", handleScroll);
      // Delay the initial scroll event dispatch to ensure correct calculation
      scrollContainer.dispatchEvent(new Event("scroll"));
      return () => scrollContainer.removeEventListener("scroll", handleScroll);
    }
  }, [divWidth, children]); // Depend on divWidth

  return isFolder ? (
    <div className="flex w-full flex-col gap-2">{children}</div>
  ) : (
    <div ref={fadeContainerRef} className="fade-container flex">
      <div ref={scrollContainerRef} className="scroll-container flex gap-2">
        {children}
      </div>
    </div>
  );
}
