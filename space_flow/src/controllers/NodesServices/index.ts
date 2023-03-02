import axios from "axios";

export async function getAll() {
    return await axios.get("http://localhost:8000/all");
}

export async function sendAll(data) {
    console.log(data);
    return await axios.post("http://localhost:8000/predict", data);
}
