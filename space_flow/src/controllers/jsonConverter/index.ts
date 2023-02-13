import axios from "axios";

export async function getPrompts() {
  const jsons = [];
  let prompts = await axios.get("http://localhost:5003/list/prompts");
  (prompts.data as Array<any>).forEach((value, index) => {
    axios
      .get("http://localhost:5003/templates/prompt", {
        params: { name: value },
      })
      .then((prompt) => {
        jsons.push({ name: value, type: "promptNode", ...prompt.data });
      });
  });
  return jsons;
}

export async function getChains() {
  const jsons = [];
  let chains = await axios.get("http://localhost:5003/list/chains");
  (chains.data as Array<any>).forEach((value, index) => {
    axios
      .get("http://localhost:5003/templates/chain", {
        params: { name: value },
      })
      .then((chain) => {
        jsons.push({ name: value, type: "chainNode", ...chain.data });
      });
  });
  return jsons;
}

export async function getAgents() {
  const jsons = [];
  let chains = await axios.get("http://localhost:5003/list/agents");
  (chains.data as Array<any>).forEach((value, index) => {
    axios
      .get("http://localhost:5003/templates/agent", {
        params: { name: value },
      })
      .then((chain) => {
        jsons.push({ name: value, type: "agentNode", ...chain.data });
      });
  });
  return jsons;
}

export async function getMemories() {
  const jsons = [];
  let memories = await axios.get("http://localhost:5003/list/memories");
  (memories.data as Array<any>).forEach((value, index) => {
    axios
      .get("http://localhost:5003/templates/memory", {
        params: { name: value },
      })
      .then((memory) => {
        jsons.push({ name: value, type: "memoryNode", ...memory.data });
      });
  });
  return jsons;
}
