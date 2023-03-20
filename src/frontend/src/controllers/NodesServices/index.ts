import { APIObjectType, sendAllProps } from '../../types/api/index';
import axios, { AxiosResponse } from "axios";

const backendUrl = process.env.BACKEND || "http://localhost:5003";

export async function getAll():Promise<AxiosResponse<APIObjectType>> {
    return await axios.get(`/all`);
}

export async function sendAll(data:sendAllProps) {
    console.log(data);
    return await axios.post(`/predict`, data);
}