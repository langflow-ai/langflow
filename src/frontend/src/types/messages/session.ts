export interface DeleteSessionParams {
  sessionId: string;
  flowId?: string;
}

export interface DeleteSessionResponse {
  message: string;
}

export interface DeleteSessionError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}
