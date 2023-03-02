import axios from "axios";

export async function getAll() {
    return await axios.get("http://localhost:5003/");
}

export async function sendAll(data) {
    console.log(data);
    return await axios.post("http://localhost:5003/predict", data);
}
