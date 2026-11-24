import type {
  AudioContent,
  FileContent,
  ImageContent,
  VideoContent,
} from "@/types/chat";
import ForwardedIconComponent from "../../common/genericIconComponent";
import { safeUrl } from "./url";

export function ImageContentDisplay({ content }: { content: ImageContent }) {
  return (
    <div className="flex flex-col gap-2">
      {content.urls?.map((url, index) => {
        const src = safeUrl(url);
        if (!src) return null;
        return (
          <img
            key={index}
            src={src}
            alt={content.caption || `Image ${index + 1}`}
            className="max-w-full rounded"
          />
        );
      })}
      {/* base64 is a fallback for when no usable URL is provided.
          `some(Boolean)` so urls=[""] or urls=[null] don't suppress the
          fallback while rendering a broken <img src=""> above. */}
      {!content.urls?.some(Boolean) && content.base64 && (
        <img
          src={`data:${content.mime_type || "image/png"};base64,${content.base64}`}
          alt={content.caption || "Image"}
          className="max-w-full rounded"
        />
      )}
      {content.caption && (
        <p className="text-xs text-muted-foreground">{content.caption}</p>
      )}
    </div>
  );
}

export function AudioContentDisplay({ content }: { content: AudioContent }) {
  return (
    <div className="flex flex-col gap-2">
      {content.urls?.map((url, index) => {
        const src = safeUrl(url);
        if (!src) return null;
        return (
          <audio key={index} controls className="w-full">
            <source src={src} type={content.mime_type} />
          </audio>
        );
      })}
      {!content.urls?.some(Boolean) && content.base64 && (
        <audio controls className="w-full">
          <source
            src={`data:${content.mime_type || "audio/mpeg"};base64,${content.base64}`}
            type={content.mime_type || "audio/mpeg"}
          />
        </audio>
      )}
      {content.transcript && (
        <p className="text-xs text-muted-foreground italic">
          {content.transcript}
        </p>
      )}
    </div>
  );
}

export function VideoContentDisplay({ content }: { content: VideoContent }) {
  return (
    <div className="flex flex-col gap-2">
      {content.urls?.map((url, index) => {
        const src = safeUrl(url);
        if (!src) return null;
        return (
          <video key={index} controls className="max-w-full rounded">
            <source src={src} type={content.mime_type} />
          </video>
        );
      })}
      {!content.urls?.some(Boolean) && content.base64 && (
        <video controls className="max-w-full rounded">
          <source
            src={`data:${content.mime_type || "video/mp4"};base64,${content.base64}`}
            type={content.mime_type || "video/mp4"}
          />
        </video>
      )}
    </div>
  );
}

export function FileContentDisplay({ content }: { content: FileContent }) {
  return (
    <div className="flex items-center gap-2">
      <ForwardedIconComponent
        name="File"
        className="h-4 w-4 text-muted-foreground"
      />
      {content.urls?.map((url, index) => {
        const label = content.filename || `Download file ${index + 1}`;
        const href = safeUrl(url);
        // URLs come from untrusted tool/model output; an unsafe scheme
        // (javascript:, data:, ...) degrades to a non-clickable label rather
        // than an anchor that runs script on click.
        if (!href) {
          return (
            <span key={index} className="text-sm text-muted-foreground">
              {label}
            </span>
          );
        }
        return (
          <a
            key={index}
            href={href}
            download={content.filename}
            className="text-sm underline text-primary hover:text-primary/80"
            target="_blank"
            rel="noopener noreferrer"
          >
            {label}
          </a>
        );
      })}
    </div>
  );
}
