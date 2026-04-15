import React from "react";
import ReactPlayer from "react-player";

interface VideoProps {
  src: string;
  title?: string;
}

export default function Video({ src, title }: VideoProps) {
  return (
    <figure className="lf-video">
      <div className="lf-video-wrapper">
        <ReactPlayer
          url={src}
          width="100%"
          height="100%"
          controls
          style={{ position: "absolute", top: 0, left: 0 }}
        />
      </div>
      {title && <figcaption className="lf-frame-caption">{title}</figcaption>}
    </figure>
  );
}
