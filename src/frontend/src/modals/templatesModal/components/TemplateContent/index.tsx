import useFlowsManagerStore from "@/stores/flowsManagerStore";

interface TemplateContentProps {
  currentTab: string;
}

export default function TemplateContent({ currentTab }: TemplateContentProps) {
  const examples = useFlowsManagerStore((state) => state.examples);
  return (
    <div className="flex-1 overflow-auto">
      <h2 className="mb-4 text-2xl font-bold">{currentTab}</h2>
      {/* Add content for each tab here */}
      <p>Content for {currentTab} goes here.</p>
    </div>
  );
}
