import { motion } from "framer-motion";

export const AnimatedConditional = ({
  children,
  isOpen,
  className,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  className?: string;
}) => {
  return (
    <motion.div
      initial={{ width: isOpen ? "auto" : 0 }}
      animate={{ width: isOpen ? "auto" : 0 }}
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
