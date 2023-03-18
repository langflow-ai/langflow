import { APIObjectType, sendAllProps } from '../../types/api/index';
import axios, { AxiosResponse } from "axios";

const backendUrl = window.sessionStorage.getItem('port') || "http://localhost:7860";

export async function getAll():Promise<AxiosResponse<APIObjectType>> {
    return await axios.get(`/all`);
}

export async function sendAll(data:sendAllProps) {
    console.log(data);
    return await axios.post(`${backendUrl}/predict`, data);
}