import React, { useState, useContext } from 'react';
import InnerForm from '../InnerForm';
import { TabsContext } from '../../../../contexts/tabsContext';
import { alertContext } from '../../../../contexts/alertContext';
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";


interface FormManagerProps {
  flow: any; 
}

const FormManager: React.FC<FormManagerProps> = ({ flow }) => {
  console.log(flow)
  const { setSuccessData, setErrorData } = useContext(alertContext);
    const { flows, tabId, uploadFlow, tabsState, saveFlow, isBuilt } =
      useContext(TabsContext);

    const isPending = tabsState[tabId]?.isPending;

    const renderFieldsFromNodes = () => {
      const { nodes, edges } = flow.data;
      
      // Find starting node (a node that is not a source in any edge)
      const childNodes = new Set(edges.map((edge: any) => edge.source));
      const startingNode = nodes.find((node: any) => !childNodes.has(node.id));

      if (!startingNode) return null; // No starting node found
      
      // Render the hierarchy starting from the startingNode
      return renderNode({ node: startingNode, children: [] });
  };
    const SaveButton = () => (
        <div className="side-bar-button">
            <ShadTooltip content="Save" side="top">
                <button
                    className={
                    "extra-side-bar-buttons " + (isPending ? "" : "button-disable")
                    }
                    onClick={(event) => {
                    saveFlow(flow);
                    setSuccessData({ title: "Changes saved successfully" });
                    }}
                >
                    <IconComponent
                    name="Save"
                    className={
                        "side-bar-button-size" +
                        (isPending ? " " : " extra-side-bar-save-disable")
                    }
                    />
                </button>
            </ShadTooltip>
        </div>
    );

    const renderNode = (nodeObj: any) => {
        const { nodes, edges } = flow.data;

        const children = edges
            .filter((edge: any) => edge.target === nodeObj.node.id)
            .map((edge: any) => ({ node: nodes.find((node: any) => node.id === edge.source), children: [] }))
            .map(child => renderNode(child));

        return (
            <div 
                key={nodeObj.node.id} 
                style={{ 
                    // border: '1px solid #e1e1e1', 
                    // borderRadius: '8px',
                    padding: '20px', 
                    margin: '10px 0',
                    // backgroundColor: '#fafafa',
                    fontSize: '16px',
                    fontWeight: '500',
                }}
            >
                <InnerForm nodeData={nodeObj.node.data} />
                {children.length > 0 && (
                    <div style={{ marginLeft: '40px' }}>
                        {children}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div style={{ overflowY: 'auto', maxHeight: '100vh', padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
            <form>
                <SaveButton />
                {renderFieldsFromNodes()}
                <SaveButton />
            </form>
        </div>
    );
};

export default FormManager;