export interface LivenessResponse {
  status: string;
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready';
  database: 'connected' | 'disconnected';
  blockchain_rpc: 'connected' | 'unavailable';
}
