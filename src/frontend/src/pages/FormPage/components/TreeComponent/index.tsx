import React from 'react';
import { Tree, DNode } from '../../treeAlgorithm'
type Props = {
    treeData: any;
};

class TreeDisplay extends React.Component<Props> {
    tree: Tree | null = null;

    constructor(props: Props) {
        super(props);
        if (props.treeData && props.treeData.data) {
            this.tree = new Tree(props.treeData);
        }
    }
    getStartNodeId(): string | null {
        for (let node of this.tree.nodes) {
            const isTargeted = this.tree.edges.some(edge => edge.source === node.id);
            if (!isTargeted) {
                return node.id;
            }
        }
        return null;
    }

    getLevel2Nodes() {
        const startNodeId = this.getStartNodeId();
        if (!startNodeId) return [];
        const startNode = this.tree.findNodeById(startNodeId);
        return this.tree.getParentNodes(startNode!);
    }

    getFlattenedChildren(node: DNode): DNode[] {
        const flattened: DNode[] = [];
    
        const gatherChildren = (n: DNode) => {
            flattened.push(n); // Pushing the current node to the list
            
            const children = this.tree.getParentNodes(n);
            children.forEach(gatherChildren);
        };
    
        gatherChildren(node);
        return flattened;
    }
    

    render() {
        if (!this.tree) {
            return <p>No tree data available.</p>;
        }

        const level2Nodes = this.getLevel2Nodes();
        return (
            <div>
                {level2Nodes.map(node => (
                    <div key={node.id} style={{ marginBottom: '20px' }}>
                        <div style={{ background: 'gray', padding: '10px', color: 'white' }}>
                            Progress: {node.type} - {node.id}
                        </div>
                        <ul>
                            {this.getFlattenedChildren(node).map(child => (
                                <li key={child.id}>
                                    {child.type} - {child.id}
                                </li>
                            ))}
                        </ul>
                    </div>
                ))}
            </div>
        );
    }
}

export default TreeDisplay;