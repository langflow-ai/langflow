import React from "react";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { VersionIcon } from "@/assets/icons/VersionIcon";
import { Button } from "@/components/ui/button";
import { FileIcon } from "@radix-ui/react-icons";

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
      <h3 className="text-md font-medium mb-3 text-primary">Agent Details</h3>
      <div className="text-sm space-y-4">
        <div className="flex items-center gap-6">
          <p className="text-xs">
            <span className="text-[#64616A] block">Created On: </span>
            <span className="text-[#444444] font-medium">
              {agentDetails.createdOn}
            </span>
          </p>
          <p className="text-xs">
            <span className="text-[#64616A] block">Last Updated On: </span>
            <span className="text-[#444444] font-medium">
              {agentDetails.lastUpdatedOn}
            </span>
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-[#444] text-xs font-medium">Description:</p>
          <p className="text-[#64616A] text-xs">{agentDetails.description}</p>
          <p className="text-[#64616A] text-xs font-medium border border-[#EFEFEF] rounded-full px-2 py-1 w-fit flex items-center gap-1">
            <VersionIcon /> Version: {agentDetails.version}
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

        {(sampleFileNames.length > 0 || sampleTexts.length > 0) && (
          <div className="p-3 border border-[#EFEFEF] rounded-md space-y-4">
            {/* Sample Input files Section (shown only when provided) */}
            {sampleFileNames.length > 0 && (
              <div className="space-y-2">
                <p className="text-[#444] text-xs font-medium">
                  Sample Input files
                </p>
                <div className="flex flex-col gap-1 mt-1">
                  {sampleFileNames.map((name, idx) => (
                    <button
                      key={`${name}-${idx}`}
                      type="button"
                      className="text-[#64616A] text-xs py-2 borde border-b border-[#EFEFEF] transition-colors flex items-center gap-2 justify-between w-full"
                      onClick={() => onPreviewSampleFile(sampleFilePaths[idx])}
                      title="Preview sample file"
                    >
                      <p className="flex items-center gap-2">
                        <FileIcon />{" "}
                        <span className="truncate max-w-[150px]">{name} </span>
                      </p>
                      <span className="text-[#731FE3] font-medium text-nowrap">
                        View File
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Sample Input Text Section (shown only when provided) */}
            {sampleTexts.length > 0 && (
              <div>
                <p className="text-[#444] text-xs font-medium">
                  Sample Input Text
                </p>
                <div className="flex flex-col mt-[12px] space-y-2">
                  {sampleTexts.map((text, idx) => (
                    <Button
                      variant="outline"
                      size="xs"
                      key={`sample-text-${idx}`}
                      type="button"
                      className="text-[#64616A] text-xs font-normal hover:text-[#350E84] px-3 py-1 rounded-[4px] transition-colors !justify-start truncate w-full"
                      onClick={() => onOpenSampleText(text, idx)}
                      title="Click to view full text"
                    >
                      {truncateText(text, 80)}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Sample Output Section (only one, shown only when provided) */}
        {/* {sampleOutput && (
          <div className="p-3 border border-[#EFEFEF] rounded-md space-y-2">
            <p className="text-[#444] text-xs font-medium">Response (Sample Output)</p>
            <div className="bg-[#F5F2FF] text-[#64616A] text-xs p-3 rounded-[4px] border border-[#EFEFEF] max-h-[220px] overflow-auto font-mono whitespace-pre-wrap">
              {sampleOutput}
            </div>
          </div>
        )} */}
      </div>
    </div>
  );
}
