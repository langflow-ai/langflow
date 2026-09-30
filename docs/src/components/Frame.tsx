import React from "react";

interface FrameProps {
  children?: React.ReactNode;
  light?: string;
  dark?: string;
  alt?: string;
  caption?: string;
}

export default function Frame({
  children,
  light,
  dark,
  alt = "",
  caption,
}: FrameProps) {
  const renderImages = () => {
    if (light && dark) {
      return (
        <>
          <img
            src={light}
            alt={alt}
            className="lf-frame-img lf-frame-img--light"
          />
          <img
            src={dark}
            alt={alt}
            className="lf-frame-img lf-frame-img--dark"
          />
        </>
      );
    }
    if (light) {
      return <img src={light} alt={alt} className="lf-frame-img" />;
    }
    return children;
  };

  return (
    <figure className="lf-frame">
      <div className="lf-frame-content">{renderImages()}</div>
      {caption && <figcaption className="lf-frame-caption">{caption}</figcaption>}
    </figure>
  );
}
