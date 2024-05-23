const isWrappedWithClass = (event: any, className: string | undefined) =>
  event.target.closest(`.${className}`);

export default isWrappedWithClass;
