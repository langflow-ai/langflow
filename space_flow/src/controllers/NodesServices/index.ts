import axios from "axios";

export async function getAll() {
    return await axios.get("http://localhost:5003/");
}
