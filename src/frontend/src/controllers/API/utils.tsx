import axios from "axios";

export async function fetchConfig() {
  try {
    const response = await axios.get("/config");
    return response.data;
  } catch (error) {
    console.error("Failed to fetch configuration:", error);
    throw error;
  }
}
