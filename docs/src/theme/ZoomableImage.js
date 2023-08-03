import React, { useState, useEffect } from "react";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";

const ZoomableImage = ({ alt, sources, style }) => {
  // add style here
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handleKeyPress = (event) => {
    if (event.key === "Escape") {
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    if (isFullscreen) {
      document.addEventListener("keydown", handleKeyPress);
    } else {
      document.removeEventListener("keydown", handleKeyPress);
    }

    return () => {
      document.removeEventListener("keydown", handleKeyPress);
    };
  }, [isFullscreen]);

  // Default style
  const defaultStyle = {
    width: "50%",
    margin: "0 auto",
    display: "flex",
    justifyContent: "center",
  };

  return (
    <div
      className={`zoomable-image ${isFullscreen ? "fullscreen" : ""}`}
      onClick={toggleFullscreen}
      style={{ ...defaultStyle, ...style }}
    >
      <ThemedImage
        className="zoomable-image-inner"
        alt={alt}
        sources={{
          light: useBaseUrl(sources.light),
          dark: useBaseUrl(sources.dark),
        }}
      />
    </div>
  );
};

export default ZoomableImage;
