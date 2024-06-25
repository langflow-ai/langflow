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

  const [aspectRatio, setAspectRatio] = useState(null);

  useEffect(() => {
    const img = new Image();
    img.src = sources.light;

    img.onload = () => {
      const width = img.width;
      const height = img.height;
      const ratio = width / height;
      setAspectRatio(ratio);
    };

    img.onerror = (error) => {
      console.error("Error loading image:", error);
    };
  }, [sources.light]);

  // Default style
  const defaultStyle = {
    width: "80%",
    aspectRatio: aspectRatio ? aspectRatio : "16/9",
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
