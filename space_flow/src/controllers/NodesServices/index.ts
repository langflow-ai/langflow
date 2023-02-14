import axios from "axios";

export async function getPrompts() {
  const promises = (await axios.get("http://localhost:5003/list/prompts")).data.map(async (value, index) => {
    const prompt = await axios.get("http://localhost:5003/templates/prompt", {
      params: { name: value },
    });
    return { name: value, type: "promptNode", ...prompt.data };
  });
  return Promise.all(promises);
}

export async function getChains() {
  const promises = (await axios.get("http://localhost:5003/list/chains")).data.map(async (value, index) => {
    const chain = await axios.get("http://localhost:5003/templates/chain", {
      params: { name: value },
    });
    return { name: value, type: "chainNode", ...chain.data };
  });
  return Promise.all(promises);
}

export async function getAgents() {
  const promises = (await axios.get("http://localhost:5003/list/agents")).data.map(async (value, index) => {
    const chain = await axios.get("http://localhost:5003/templates/agent", {
      params: { name: value },
    });
    return { name: value, type: "agentNode", ...chain.data };
  });
  return Promise.all(promises);
}

export async function getMemories() {
  const promises = (await axios.get("http://localhost:5003/list/memories")).data.map(async (value, index) => {
    const chain = await axios.get("http://localhost:5003/templates/memory", {
      params: { name: value },
    });
    return { name: value, type: "memoryNode", ...chain.data };
  });
  return Promise.all(promises);
}

export async function getTools() {
  const promises = (await axios.get("http://localhost:5003/list/tools")).data.map(async (value, index) => {
    const prompt = await axios.get("http://localhost:5003/templates/tool", {
      params: { name: value },
    });
    return { name: value, type: "toolNode", ...prompt.data };
  });
  return Promise.all(promises);
}

export async function getModels() {
  const promises = (await axios.get("http://localhost:5003/list/llms")).data.map(async (value, index) => {
    const prompt = await axios.get("http://localhost:5003/templates/llm", {
      params: { name: value },
    });
    return { name: value, type: "modelNode", ...prompt.data };
  });
  return Promise.all(promises);
}
