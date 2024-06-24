import { AnimatePresence, motion } from "framer-motion";
export default function Xmark({ initial = true, isVisible, className }) {
  return (
    <AnimatePresence initial={initial}>
      {isVisible && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className={"CheckIcon " + className}
        >
          <motion.path
            initial={{ pathLength: 0, pathOffset: 1, strokeLinecap: "butt" }}
            animate={{ pathLength: 1, pathOffset: 0, strokeLinecap: "round" }}
            exit={{ pathLength: 0, pathOffset: 1, strokeLinecap: "butt" }}
            transition={{
              type: "tween",
              duration: 0.3,
              ease: isVisible ? "easeOut" : "easeIn",
              delay: 0.2,
            }}
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18 6 6 18"
          />
          <motion.path
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            exit={{ pathLength: 0 }}
            transition={{
              type: "tween",
              duration: 0.3,
              ease: isVisible ? "easeOut" : "easeIn",
            }}
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m6 6 12 12"
          />
        </svg>
      )}
    </AnimatePresence>
  );
}
