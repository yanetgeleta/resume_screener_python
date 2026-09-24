"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import {
  getAuthToken,
  getRefreshToken,
  refreshTokenApi,
  getStoredUserEmail,
  clearAuthTokens,
  loginApi,
  registerApi,
  logoutApi,
} from "./api";

interface AuthContextType {
  token: string;
  email: string;
  isAuthenticated: boolean;
  isLoading: boolean;
  isRefreshing: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, companyName: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshAuth = async (): Promise<boolean> => {
    const refresh = getRefreshToken();
    if (!refresh) return false;
    setIsRefreshing(true);
    try {
      const newToken = await refreshTokenApi();
      setToken(newToken);
      setEmail(getStoredUserEmail());
      return true;
    } catch (err) {
      console.warn("Auto/manual token refresh failed:", err);
      return false;
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    const syncState = () => {
      setToken(getAuthToken());
      setEmail(getStoredUserEmail());
    };

    window.addEventListener("auth_token_changed", syncState);

    // Initial load: if refresh token exists, proactively refresh on opening localhost
    const initAuth = async () => {
      const currentToken = getAuthToken();
      const currentRefresh = getRefreshToken();
      const currentEmail = getStoredUserEmail();

      setToken(currentToken);
      setEmail(currentEmail);

      if (currentRefresh) {
        try {
          const freshToken = await refreshTokenApi();
          setToken(freshToken);
        } catch {
          // Keep current token if valid or clear handled by refreshTokenApi
        }
      }
      setIsLoading(false);
    };

    initAuth();

    return () => {
      window.removeEventListener("auth_token_changed", syncState);
    };
  }, []);

  const login = async (userEmail: string, pass: string) => {
    const res = await loginApi(userEmail, pass);
    setToken(res.access);
    setEmail(userEmail);
  };

  const register = async (userEmail: string, companyName: string, pass: string) => {
    await registerApi(userEmail, companyName, pass);
    await login(userEmail, pass);
  };

  const logout = async () => {
    await logoutApi();
    setToken("");
    setEmail("");
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        email,
        isAuthenticated: !!token,
        isLoading,
        isRefreshing,
        login,
        register,
        logout,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
