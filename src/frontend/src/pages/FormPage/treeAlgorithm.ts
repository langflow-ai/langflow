
export type DNode = {
    id: string;
    type: string;
    data: {
        type: string;
        node: {
            template: any;
        };
    };
    position: {
        x: number;
        y: number;
    };
};

type Edge = {
    source: string;
    target: string;
};

export class Tree {
    nodes: DNode[];
    edges: Edge[];

    constructor(treeJson: any) {
        this.nodes = treeJson.data.nodes;
        this.edges = treeJson.data.edges;
    }

    findNodeById(nodeId: string): DNode | undefined {
        return this.nodes.find(node => node.id === nodeId);
    }

    getParentNodes(childNode: DNode): DNode[] {
        const parentEdges = this.edges.filter(edge => edge.target === childNode.id);
        return parentEdges.map(edge => this.findNodeById(edge.source)!);
    }

    displayNodeHierarchy(node: DNode, level: number = 0) {
        const parentNodes = this.getParentNodes(node);
        parentNodes.forEach(parentNode => this.displayNodeHierarchy(parentNode, level + 1));
    }

    displayTreeFromNode(startNodeId: string) {
        const startNode = this.findNodeById(startNodeId);
        if (startNode) {
            this.displayNodeHierarchy(startNode);
        } else {
            console.error('Node not found');
        }
    }
}

import { SAMPLE_ONE, SAMPLE_TWO } from "../../constants/templates";

const tree = new Tree(SAMPLE_TWO);
tree.displayTreeFromNode("VectorStoreAgent-lrDhT");
