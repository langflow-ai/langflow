import { APIObjectType, sendAllProps } from '../../types/api/index';
import axios, { AxiosResponse } from "axios";

export async function getAll():Promise<AxiosResponse<APIObjectType>> {
    return await axios.get(`/all`);
}

export async function sendAll(data:sendAllProps) {
    return await axios.post(`/predict`, data);
}