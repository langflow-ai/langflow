import React, { useState, useEffect } from 'react';
import { FlowType } from "../../../../types/flow";
import TreeDisplay from "../TreeComponent";
import NewProjectModal from "../../../../modals/NewProjectModal";

export default function Page({flow}: {flow: FlowType}) {
    const [showModal, setShowModal] = useState(false);

    useEffect(() => {
        const shouldShowModal = flow.data === null || (flow.data && flow.data.nodes.length === 0 && flow.data.edges.length === 0);
        setShowModal(shouldShowModal);
    }, [flow]);

    return (
        <div>
            <TreeDisplay treeData={flow} />
            {showModal && 1}
            {showModal && 
            <NewProjectModal view="templates" flow={flow} open>{}</NewProjectModal>}
        </div>
    );
}
