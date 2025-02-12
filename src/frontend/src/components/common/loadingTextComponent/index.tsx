import { useEffect, useState } from "react";

const LoadingTextComponent = ({ text }: { text: string }) => {
  const [dots, setDots] = useState(".");

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prevDots) => (prevDots === "..." ? "" : `${prevDots}.`));
    }, 300);

    return () => {
      clearInterval(interval);
    };
  }, []);

  return <span>{`${text}${dots}`}</span>;
};

export default LoadingTextComponent;
