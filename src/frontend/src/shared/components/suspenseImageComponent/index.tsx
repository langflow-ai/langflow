type SuspenseImageComponentProps = { src: string };

const imgCache = {
  __cache: {},
  read(src) {
    if (!this.__cache[src]) {
      this.__cache[src] = new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          this.__cache[src] = true;
          resolve(true);
        };
        img.onerror = () => {
          delete this.__cache[src]; // Remove failed cache entry
          reject(new Error("Image failed to load"));
        };
        img.src = src;
      });
    }
    if (this.__cache[src] instanceof Promise) {
      throw this.__cache[src];
    }
    return this.__cache[src];
  },
};

const SuspenseImageComponent = ({
  src,
  ...rest
}: SuspenseImageComponentProps) => {
  try {
    imgCache.read(src);
  } catch (promise) {
    if (promise instanceof Promise) {
      throw promise;
    }
    throw new Error("Unexpected error in image loading");
  }

  return <img src={src} {...rest} />;
};

export default SuspenseImageComponent;
