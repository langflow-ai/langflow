import { motion } from "framer-motion";

export const AnimatedConditional = ({
  children,
  isOpen,
}: {
  children: React.ReactNode;
  isOpen: boolean;
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
    >
      {children}
    </motion.div>
  );
};
