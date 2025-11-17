import React from "react";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";

type AgentDetails = {
  createdOn: string;
  lastUpdatedOn: string;
  description: string;
  version: string;
  tags: string[];
  name: string;
};

interface AgentDetailsPanelProps {
  agentDetails: AgentDetails;
  sampleFileNames: string[];
  sampleFilePaths: string[];
  sampleTexts: string[];
  sampleOutput?: string;
  onPreviewSampleFile: (filePathOrName: string) => void;
  onOpenSampleText: (text: string, index: number) => void;
  onOpenSampleOutput?: (text: string) => void;
}

const getTagTitle = (tagId: string): string => {
  const tag = MARKETPLACE_TAGS.find((t) => t.id === tagId);
  return tag ? tag.title : tagId;
};

const truncateText = (text: string, maxLength: number = 80): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
};

export function AgentDetailsPanel({
  agentDetails,
  sampleFileNames,
  sampleFilePaths,
  sampleTexts,
  sampleOutput,
  onPreviewSampleFile,
  onOpenSampleText,
  onOpenSampleOutput,
}: AgentDetailsPanelProps) {
  return (
    <div className="bg-white rounded-lg p-4 flex-1 overflow-y-auto">
      <h3 className="text-sm font-medium mb-4 text-[#444]">Agent Details</h3>
      <div className="text-sm space-y-4">
        <p className="">
          <span className="text-[#64616A] text-xs">
            Created On: {agentDetails.createdOn} {"  "}
          </span>
          {"  "}
          <span className="text-[#64616A] text-xs">
            Last Updated On: {agentDetails.lastUpdatedOn}
          </span>
        </p>

        <div className="space-y-2">
          <p className="text-[#444] text-xs font-medium">Description:</p>
          <p className="text-[#64616A] text-xs">{agentDetails.description}</p>
          <p className="text-[#64616A] text-xs font-medium">
            Version: {agentDetails.version}
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-[#444] text-xs font-medium">Domain:</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {agentDetails.tags.map((tag: string, index: number) => (
              <span
                key={index}
                className="bg-[#F5F2FF] text-[#64616A] text-xs px-2 py-1 rounded-[4px]"
              >
                {getTagTitle(tag)}
              </span>
            ))}
          </div>
        </div>

        {/* Sample Input files Section (shown only when provided) */}
        {sampleFileNames.length > 0 && (
          <div className="space-y-2">
            <p className="text-[#444] text-xs font-medium">Sample Input files:</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {sampleFileNames.map((name, idx) => (
                <button
                  key={`${name}-${idx}`}
                  type="button"
                  className="bg-[#F5F2FF] text-[#64616A] text-xs px-2 py-1 rounded-[4px] hover:bg-[#EAE6FF] transition-colors"
                  onClick={() => onPreviewSampleFile(sampleFilePaths[idx])}
                  title="Preview sample file"
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sample Input Text Section (shown only when provided) */}
        {sampleTexts.length > 0 && (
          <div className="space-y-2">
            <p className="text-[#444] text-xs font-medium">Sample Input Text:</p>
            <div className="flex flex-col gap-2 mt-1">
              {sampleTexts.map((text, idx) => (
                <button
                  key={`sample-text-${idx}`}
                  type="button"
                  className="bg-[#F5F2FF] text-[#64616A] text-xs px-3 py-2 rounded-[4px] hover:bg-[#EAE6FF] transition-colors text-left break-words"
                  onClick={() => onOpenSampleText(text, idx)}
                  title="Click to view full text"
                >
                  {truncateText(text, 80)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sample Output Section (only one, shown only when provided) */}
        {sampleOutput && (
          <div className="space-y-2">
            <p className="text-[#444] text-xs font-medium">Sample Output:</p>
            <button
              type="button"
              className="bg-[#F5F2FF] text-[#64616A] text-xs px-3 py-2 rounded-[4px] hover:bg-[#EAE6FF] transition-colors text-left break-words"
              onClick={() => onOpenSampleOutput?.(sampleOutput)}
              title="Click to view full output"
            >
              {truncateText(sampleOutput, 80)}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}