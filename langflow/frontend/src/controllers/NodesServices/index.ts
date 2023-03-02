import { APIObjectType, sendAllProps } from '../../types/api/index';
import axios, { AxiosResponse } from "axios";

export async function getAll():Promise<AxiosResponse<APIObjectType>> {
    return await axios.get("http://localhost:5003/");
}

export async function sendAll(data:sendAllProps) {
    console.log(data);
    return await axios.post("http://localhost:5003/predict", data);
}
