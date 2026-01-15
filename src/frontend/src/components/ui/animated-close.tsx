import { motion } from "framer-motion";

export const AnimatedConditional = ({
  children,
  isOpen,
  className,
  width,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  className?: string;
  width?: string | number;
}) => {
  const widthValue = width ?? (isOpen ? "auto" : 0);

  return (
    <motion.div
      initial={{ width: isOpen ? widthValue : 0 }}
      animate={{ width: isOpen ? widthValue : 0 }}
      exit={{ width: 0 }}
      transition={{
        duration: 0.3,
        ease: "easeInOut",
      }}
      style={{
        overflow: "hidden",
        whiteSpace: "nowrap",
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
};
