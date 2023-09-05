import React, { useState, useEffect } from 'react';
import ParameterComponent from '../../../../CustomNodes/GenericNode/components/parameterComponent';
import { nodeColors, nodeIconsLucide } from "../../../../utils/styleUtils";
import { toTitleCase } from "../../../../utils/utils";
import { useContext } from 'react';
import { typesContext } from "../../../../contexts/typesContext";
import { TabsContext } from '../../../../contexts/tabsContext';
import { cloneDeep } from "lodash";
import { cleanEdges } from "../../../../utils/reactflowUtils";
import { NodeToolbar, useUpdateNodeInternals } from "reactflow";
import { NodeDataType } from '../../../../types/flow';
import Collapsible from '../CollapsibleComponent';
interface InnerFormProps {
    nodeData: any;  // Type this based on your needs
}

const InnerForm: React.FC<InnerFormProps> = ({ nodeData }: {nodeData:NodeDataType}) => {
    const [data, setData] = useState(nodeData);
    const updateNodeInternals = useUpdateNodeInternals();
    const { updateFlow, flows, tabId } = useContext(TabsContext);
    const { types, deleteNode, reactFlowInstance } = useContext(typesContext);
    useEffect(() => {
        console.log(nodeData)
        nodeData.node = data.node;
        let myFlow = flows.find((flow) => flow.id === tabId);
        if (reactFlowInstance && myFlow) {
          let flow = cloneDeep(myFlow);
          flow.data = reactFlowInstance.toObject();
          cleanEdges({
            flow: {
              edges: flow.data.edges,
              nodes: flow.data.nodes,
            },
            updateEdge: (edge) => {
              flow.data.edges = edge;
              reactFlowInstance.setEdges(edge);
              updateNodeInternals(data.id);
            },
          });
          console.log("updateFlow")
          updateFlow(flow);
        }
      }, [data]);

    const requiredParameters = Object.keys(data.node.template)
      .filter(t => t.charAt(0) !== "_" && data.node.template[t].show && !data.node.template[t].advanced && data.node.template[t].required && data.node.template[t].form);

    const nonRequiredParameters = Object.keys(data.node.template)
      .filter(t => t.charAt(0) !== "_" && data.node.template[t].show && !data.node.template[t].advanced && !data.node.template[t].required && data.node.template[t].form);

    return (
        <div className="bg-gray-100 p-5 rounded-lg border border-gray-300 max-w-xl mx-auto">
            <h2 className='text-xl font-semibold text-gray-800 mb-2'>{data.node.display_name}</h2>
            <p className='text-base text-gray-600 mb-5'>{data.node.description}</p>

            {requiredParameters.map((t, idx) => (
                <ParameterComponent
                    key={
                        (data.node.template[t].input_types?.join(";") ??
                            data.node.template[t].type) +
                        "|" +
                        t +
                        "|" +
                        data.id
                    }
                    data={data}
                    setData={setData}
                    color={
                        nodeColors[types[data.node.template[t].type]] ??
                        nodeColors[data.node.template[t].type] ??
                        nodeColors.unknown
                    }
                    title={
                        data.node.template[t].display_name
                            ? data.node.template[t].display_name
                            : data.node.template[t].name
                                ? toTitleCase(data.node.template[t].name)
                                : toTitleCase(t)
                    }
                    info={data.node.template[t].info}
                    name={t}
                    tooltipTitle={
                        data.node.template[t].input_types?.join("\n") ??
                        data.node.template[t].type
                    }
                    required={data.node.template[t].required}
                    id={
                        (data.node.template[t].input_types?.join(";") ??
                            data.node.template[t].type) +
                        "|" +
                        t +
                        "|" +
                        data.id
                    }
                    left={true}
                    type={data.node.template[t].type}
                    optionalHandle={data.node.template[t].input_types}
                />
            ))}

            <Collapsible title="Additional Options">
                {nonRequiredParameters.map((t, idx) => (
                    <ParameterComponent
                        key={
                            (data.node.template[t].input_types?.join(";") ??
                                data.node.template[t].type) +
                            "|" +
                            t +
                            "|" +
                            data.id
                        }
                        data={data}
                        setData={setData}
                        color={
                            nodeColors[types[data.node.template[t].type]] ??
                            nodeColors[data.node.template[t].type] ??
                            nodeColors.unknown
                        }
                        title={
                            data.node.template[t].display_name
                                ? data.node.template[t].display_name
                                : data.node.template[t].name
                                    ? toTitleCase(data.node.template[t].name)
                                    : toTitleCase(t)
                        }
                        info={data.node.template[t].info}
                        name={t}
                        tooltipTitle={
                            data.node.template[t].input_types?.join("\n") ??
                            data.node.template[t].type
                        }
                        required={data.node.template[t].required}
                        id={
                            (data.node.template[t].input_types?.join(";") ??
                                data.node.template[t].type) +
                            "|" +
                            t +
                            "|" +
                            data.id
                        }
                        left={true}
                        type={data.node.template[t].type}
                        optionalHandle={data.node.template[t].input_types}
                    />
                ))}
            </Collapsible>
            
        </div>
    );
}

export default InnerForm;
