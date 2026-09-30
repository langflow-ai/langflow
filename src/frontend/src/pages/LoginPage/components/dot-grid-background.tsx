import { useEffect, useRef } from "react";

const DOT_SPACING = 24;
const INTERACTION_RADIUS = 160;

type Dot = {
  x: number;
  y: number;
  baseX: number;
  baseY: number;
  radius: number;
};

export default function DotGridBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotionMedia = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );
    const colorSchemeMedia = window.matchMedia("(prefers-color-scheme: dark)");
    let reducedMotion = reducedMotionMedia.matches;
    const themeElement = document.getElementById("body");
    let animationFrame = 0;
    let dots: Dot[] = [];
    let viewportWidth = 0;
    let viewportHeight = 0;
    const pointer = { x: -1000, y: -1000 };

    const draw = () => {
      context.clearRect(0, 0, viewportWidth, viewportHeight);
      const isDark =
        themeElement?.classList.contains("dark") ?? colorSchemeMedia.matches;

      dots.forEach((dot) => {
        const deltaX = pointer.x - dot.baseX;
        const deltaY = pointer.y - dot.baseY;
        const distance = Math.hypot(deltaX, deltaY);
        let targetX = dot.baseX;
        let targetY = dot.baseY;
        let targetRadius = 1;

        if (!reducedMotion && distance < INTERACTION_RADIUS) {
          const force = (INTERACTION_RADIUS - distance) / INTERACTION_RADIUS;
          const easedForce = force * force;
          targetX += deltaX * easedForce * 0.35;
          targetY += deltaY * easedForce * 0.35;
          targetRadius += easedForce * 2;
        }

        dot.x += (targetX - dot.x) * 0.15;
        dot.y += (targetY - dot.y) * 0.15;
        dot.radius += (targetRadius - dot.radius) * 0.15;

        const intensity = Math.min(1, (dot.radius - 1) / 2);
        // Light dots on dark canvas; darker dots on light canvas.
        const shade = isDark
          ? Math.round(51 + (200 - 51) * intensity)
          : Math.round(200 - (200 - 110) * intensity);
        context.beginPath();
        context.arc(dot.x, dot.y, dot.radius, 0, Math.PI * 2);
        context.fillStyle = `rgb(${shade} ${shade} ${shade})`;
        context.fill();
      });

      if (!reducedMotion) {
        animationFrame = window.requestAnimationFrame(draw);
      }
    };

    const resize = () => {
      const pixelRatio = window.devicePixelRatio || 1;
      viewportWidth = document.documentElement.clientWidth;
      viewportHeight = document.documentElement.clientHeight;
      canvas.width = viewportWidth * pixelRatio;
      canvas.height = viewportHeight * pixelRatio;
      canvas.style.width = `${viewportWidth}px`;
      canvas.style.height = `${viewportHeight}px`;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

      dots = [];
      const columns = Math.ceil(viewportWidth / DOT_SPACING) + 1;
      const rows = Math.ceil(viewportHeight / DOT_SPACING) + 1;

      for (let column = 0; column < columns; column += 1) {
        for (let row = 0; row < rows; row += 1) {
          const x = column * DOT_SPACING;
          const y = row * DOT_SPACING;
          dots.push({ x, y, baseX: x, baseY: y, radius: 1 });
        }
      }

      if (reducedMotion) {
        draw();
      }
    };

    const redrawStaticCanvas = () => {
      if (reducedMotion) {
        draw();
      }
    };

    const handleReducedMotionChange = (event: MediaQueryListEvent) => {
      reducedMotion = event.matches;
      window.cancelAnimationFrame(animationFrame);
      animationFrame = 0;

      if (reducedMotion) {
        pointer.x = -1000;
        pointer.y = -1000;
        dots.forEach((dot) => {
          dot.x = dot.baseX;
          dot.y = dot.baseY;
          dot.radius = 1;
        });
      }
      draw();
    };

    const handlePointerMove = (event: PointerEvent) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
    };

    const resetPointer = () => {
      pointer.x = -1000;
      pointer.y = -1000;
    };

    resize();
    if (!reducedMotion) {
      draw();
    }
    const themeObserver = themeElement
      ? new MutationObserver(redrawStaticCanvas)
      : null;
    if (themeElement) {
      themeObserver?.observe(themeElement, {
        attributeFilter: ["class"],
        attributes: true,
      });
    }
    colorSchemeMedia.addEventListener?.("change", redrawStaticCanvas);
    reducedMotionMedia.addEventListener?.("change", handleReducedMotionChange);
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", handlePointerMove);
    document.documentElement.addEventListener("pointerleave", resetPointer);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      themeObserver?.disconnect();
      colorSchemeMedia.removeEventListener?.("change", redrawStaticCanvas);
      reducedMotionMedia.removeEventListener?.(
        "change",
        handleReducedMotionChange,
      );
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", handlePointerMove);
      document.documentElement.removeEventListener(
        "pointerleave",
        resetPointer,
      );
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0"
    />
  );
}
