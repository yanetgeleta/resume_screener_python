"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import {
  getAuthToken,
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
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, companyName: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setToken(getAuthToken());
    setEmail(getStoredUserEmail());
    setIsLoading(false);
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
        login,
        register,
        logout,
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
