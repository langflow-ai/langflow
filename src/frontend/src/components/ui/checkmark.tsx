import { AnimatePresence, motion } from "framer-motion";
export default function Checkmark({ initial = true, isVisible, className }) {
  return (
    <AnimatePresence initial={initial}>
      {isVisible && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className={"CheckIcon " + className}
        >
          <motion.path
            initial={{ pathLength: 0, pathOffset: 1 }}
            animate={{ pathLength: 1, pathOffset: 0 }}
            exit={{ pathLength: 0, pathOffset: 1 }}
            transition={{
              type: "tween",
              duration: 0.3,
              ease: isVisible ? "easeOut" : "easeIn",
            }}
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20 6 9 17l-5-5"
          />
        </svg>
      )}
    </AnimatePresence>
  );
}
