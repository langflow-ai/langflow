export interface UpstreamOutput {
  nodeId: string;
  nodeSlug: string;
  nodeName: string;
  nodeColor?: string;
  outputName: string;
  outputDisplayName: string;
  outputType: string;
  lastValue?: unknown;
}

export interface ParsedReference {
  nodeSlug: string;
  outputName: string;
  dotPath?: string;
  fullPath: string;
  startIndex: number;
  endIndex: number;
}

export interface ReferenceState {
  nodeReferenceSlugs: Record<string, string>; // nodeId -> slug
  getUpstreamOutputs: (nodeId: string) => UpstreamOutput[];
  lastOutputValues: Record<string, Record<string, unknown>>; // nodeId -> outputName -> value
}
