import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { AuthPrincipal, AuthContextType, AuthStatus } from '@/types/auth';
import { tokenStore } from '@/services/tokenStore';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function parseJwtPayload(token: string): Partial<AuthPrincipal> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const parsed = JSON.parse(jsonPayload);

    // Extract roles from claims (roles, realm_access, or scope)
    const roles: string[] = [];
    if (Array.isArray(parsed.roles)) {
      roles.push(...parsed.roles.map(String));
    }
    if (parsed.realm_access?.roles && Array.isArray(parsed.realm_access.roles)) {
      roles.push(...parsed.realm_access.roles.map(String));
    }
    if (typeof parsed.scope === 'string') {
      parsed.scope.split(' ').forEach((s: string) => {
        if (s.startsWith('role:')) roles.push(s.slice(5));
      });
    }

    const normalizedRoles = Array.from(new Set(roles.map((r) => r.toLowerCase())));

    return {
      sub: parsed.sub || 'anonymous',
      roles: normalizedRoles,
      issuerId: (parsed.issuer_id || parsed.institution_id || '').toLowerCase() || undefined,
      verifierId: parsed.verifier_id || parsed.org_id || parsed.sub,
      email: parsed.email,
      exp: parsed.exp,
    };
  } catch (err) {
    console.warn('Failed to parse JWT payload in memory:', err);
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(() => tokenStore.getToken());
  const [user, setUser] = useState<AuthPrincipal | null>(() => {
    const current = tokenStore.getToken();
    if (!current) return null;
    const parsed = parseJwtPayload(current);
    return parsed ? (parsed as AuthPrincipal) : null;
  });
  const [status, setStatus] = useState<AuthStatus>(() => (token ? 'authenticated' : 'unauthenticated'));
  const [authError, setAuthError] = useState<string | null>(null);

  // Subscribe to in-memory token changes (e.g. cleared on 401 by API client)
  useEffect(() => {
    const unsubscribe = tokenStore.subscribe((newToken) => {
      setTokenState(newToken);
      if (newToken) {
        const parsed = parseJwtPayload(newToken);
        if (parsed) {
          setUser(parsed as AuthPrincipal);
          setStatus('authenticated');
        } else {
          setUser(null);
          setStatus('unauthenticated');
        }
      } else {
        setUser(null);
        setStatus((prev) => (prev === 'authenticated' ? 'expired' : 'unauthenticated'));
      }
    });

    return unsubscribe;
  }, []);

  const login = useCallback((jwtToken: string) => {
    const trimmed = jwtToken.trim();
    const parsed = parseJwtPayload(trimmed);
    if (!parsed || !parsed.sub) {
      setAuthError('Invalid JWT token structure or payload.');
      return;
    }
    setAuthError(null);
    tokenStore.setToken(trimmed);
  }, []);

  const logout = useCallback(() => {
    tokenStore.clearToken();
    setAuthError(null);
    setStatus('unauthenticated');
  }, []);

  const clearError = useCallback(() => {
    setAuthError(null);
  }, []);

  const hasRole = useCallback(
    (role: string): boolean => {
      if (!user) return false;
      const target = role.toLowerCase();
      return user.roles.includes('admin') || user.roles.includes(target);
    },
    [user]
  );

  const isAdmin = useMemo(() => Boolean(user?.roles.includes('admin')), [user]);
  const isIssuer = useMemo(() => Boolean(isAdmin || user?.roles.includes('issuer')), [isAdmin, user]);
  const isVerifier = useMemo(() => Boolean(isAdmin || user?.roles.includes('verifier')), [isAdmin, user]);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      status,
      hasRole,
      isIssuer,
      isAdmin,
      isVerifier,
      login,
      logout,
      authError,
      clearError,
    }),
    [user, token, status, hasRole, isIssuer, isAdmin, isVerifier, login, logout, authError, clearError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

const defaultAuthContext: AuthContextType = {
  user: null,
  token: null,
  isAuthenticated: false,
  status: 'unauthenticated',
  hasRole: () => false,
  isIssuer: false,
  isAdmin: false,
  isVerifier: false,
  login: () => {},
  logout: () => {},
  authError: null,
  clearError: () => {},
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  return context || defaultAuthContext;
};
