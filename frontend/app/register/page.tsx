"use client";

import { useAuth } from "@/lib/useAuth";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Building,
  Loader2,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useState } from "react";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !email.trim() || !password) return;

    setErrorMsg(null);
    setIsLoading(true);

    try {
      await register(email.trim(), companyName.trim(), password);
      router.push("/");
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Registration failed. Please check your details.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center mx-auto shadow-xl shadow-blue-500/20">
            <Bot className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
            Create a Company Account
          </h2>
          <p className="text-xs text-zinc-400 max-w-xs mx-auto">
            Set up your organization to screen resumes and ask AI recruiter
            questions.
          </p>
        </div>

        {/* Register Form Container */}
        <div className="p-8 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 shadow-2xl backdrop-blur-xl space-y-6">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label
                htmlFor="companyName"
                className="block text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5"
              >
                <Building className="w-3.5 h-3.5 text-zinc-400" />
                Company Name
              </label>
              <input
                id="companyName"
                type="text"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Recruiting Inc."
                className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
              >
                Work Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="recruiter@acme.com"
                className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="•••••••• (Min 8 chars)"
                className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
              />
            </div>

            <button
              type="submit"
              disabled={
                isLoading || !companyName.trim() || !email.trim() || !password
              }
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 disabled:opacity-50 text-white font-medium text-xs transition-all shadow-lg shadow-blue-600/20 cursor-pointer pt-3"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <UserPlus className="w-4 h-4" />
                  <span>Register &amp; Continue</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-zinc-800 text-center text-xs text-zinc-400">
            <span>Already have an account? </span>
            <Link
              href="/login"
              className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
