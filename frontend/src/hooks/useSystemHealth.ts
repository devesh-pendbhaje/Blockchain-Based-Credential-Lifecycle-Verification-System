import { useState, useEffect, useCallback } from 'react';
import { healthApi } from '@/services/healthApi';
import { ReadinessResponse } from '@/types/health';
import { AppError } from '@/types/api';

export function useSystemHealth() {
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AppError | null>(null);

  const checkHealth = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await healthApi.getReadiness();
      setReadiness(data);
    } catch (err) {
      setError(err as AppError);
      setReadiness(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    // Poll every 30 seconds for live status
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return {
    readiness,
    isLoading,
    error,
    isOnline: readiness !== null && readiness.status === 'ready',
    isDatabaseConnected: readiness?.database === 'connected',
    isBlockchainConnected: readiness?.blockchain_rpc === 'connected',
    refresh: checkHealth,
  };
}
