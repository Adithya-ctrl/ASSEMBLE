"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ApiRequestError } from "./api";
import { authApi } from "./auth-api";
import { isAuthenticationRequired, sessionExpiryDelay, sessionHasExpired } from "./auth-session";
import type { AuthSession, LoginInput, PasswordChangeInput, ProfileInput, SignupInput } from "./auth-types";
import { isAbortError } from "./ui";

export type IdentityStatus = "bootstrapping" | "guest" | "authenticated" | "working" | "error";

export interface IdentityError {
  code: string;
  message: string;
  status: number;
  details: Record<string, unknown>;
}

interface IdentityContextValue {
  session: AuthSession | null;
  status: IdentityStatus;
  error: IdentityError | null;
  liveStatus: string;
  login: (input: LoginInput) => Promise<boolean>;
  signup: (input: SignupInput) => Promise<boolean>;
  logout: () => Promise<boolean>;
  refreshSession: () => Promise<boolean>;
  updateProfile: (input: ProfileInput) => Promise<boolean>;
  changePassword: (input: PasswordChangeInput) => Promise<boolean>;
  invalidateSession: (message?: string) => void;
  invalidateCommunityAccess: (communityId: string) => void;
  clearError: () => void;
  announce: (message: string) => void;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

function toIdentityError(error: unknown): IdentityError {
  if (error instanceof ApiRequestError) {
    return { code: error.code, message: error.message, status: error.status, details: error.details };
  }
  return { code: "REQUEST_FAILED", message: "ASSEMBLE received an unexpected identity response.", status: 0, details: {} };
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<IdentityStatus>("bootstrapping");
  const [error, setError] = useState<IdentityError | null>(null);
  const [liveStatus, setLiveStatus] = useState("Checking for a local ASSEMBLE session.");
  const controllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);

  const begin = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    generationRef.current += 1;
    setError(null);
    return { controller, generation: generationRef.current };
  }, []);

  const current = useCallback((generation: number, controller: AbortController) => (
    generationRef.current === generation && controllerRef.current === controller && !controller.signal.aborted
  ), []);

  const clearCachedSession = useCallback((message: string, nextError: IdentityError | null = null) => {
    setSession(null);
    setStatus("guest");
    setError(nextError);
    setLiveStatus(message);
  }, []);

  const invalidateSession = useCallback((message = "Your local session is no longer active. Sign in again.") => {
    generationRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    clearCachedSession(message);
  }, [clearCachedSession]);

  const invalidateCommunityAccess = useCallback((communityId: string) => {
    setSession((active) => active ? {
      ...active,
      memberships: active.memberships.filter((membership) => membership.community_id !== communityId),
    } : active);
  }, []);

  const refreshSession = useCallback(async (): Promise<boolean> => {
    const { controller, generation } = begin();
    setStatus((value) => value === "bootstrapping" ? value : "working");
    try {
      const next = await authApi.getSession(controller.signal);
      if (!current(generation, controller)) return false;
      if (sessionHasExpired(next)) {
        clearCachedSession("Your local session expired. Sign in again.");
        return false;
      }
      setSession(next);
      setStatus("authenticated");
      setLiveStatus(`Signed in as ${next.user.display_name ?? next.user.username}.`);
      return true;
    } catch (requestError) {
      if (!current(generation, controller) || isAbortError(requestError)) return false;
      const nextError = toIdentityError(requestError);
      if (isAuthenticationRequired(nextError)) {
        clearCachedSession("No local ASSEMBLE session is active.");
        return false;
      }
      setSession(null);
      setStatus("error");
      setError(nextError);
      setLiveStatus(`Identity check failed. ${nextError.message}`);
      return false;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [begin, clearCachedSession, current]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshSession(), 0);
    return () => {
      window.clearTimeout(timer);
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [refreshSession]);

  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(
      () => invalidateSession("Your local session expired. Sign in again."),
      sessionExpiryDelay(session),
    );
    return () => window.clearTimeout(timer);
  }, [invalidateSession, session]);

  const runSessionAction = useCallback(async (
    task: (signal: AbortSignal) => Promise<AuthSession>,
    successMessage: (next: AuthSession) => string,
  ): Promise<boolean> => {
    const { controller, generation } = begin();
    setStatus("working");
    try {
      const next = await task(controller.signal);
      if (!current(generation, controller)) return false;
      if (sessionHasExpired(next)) {
        clearCachedSession("The returned session had already expired. Sign in again.");
        return false;
      }
      setSession(next);
      setStatus("authenticated");
      setLiveStatus(successMessage(next));
      return true;
    } catch (requestError) {
      if (!current(generation, controller) || isAbortError(requestError)) return false;
      const nextError = toIdentityError(requestError);
      if (isAuthenticationRequired(nextError)) {
        clearCachedSession(nextError.message, nextError);
        return false;
      }
      setStatus(session ? "authenticated" : "guest");
      setError(nextError);
      setLiveStatus(nextError.message);
      return false;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [begin, clearCachedSession, current, session]);

  const login = useCallback((input: LoginInput) => runSessionAction(
    (signal) => authApi.login(input, signal),
    (next) => `Signed in as ${next.user.display_name ?? next.user.username}.`,
  ), [runSessionAction]);

  const signup = useCallback((input: SignupInput) => runSessionAction(
    (signal) => authApi.signup(input, signal),
    (next) => `Account created for ${next.user.display_name ?? next.user.username}.`,
  ), [runSessionAction]);

  const changePassword = useCallback((input: PasswordChangeInput) => runSessionAction(
    (signal) => authApi.changePassword(input, signal),
    () => "Password changed and the local session was rotated.",
  ), [runSessionAction]);

  const updateProfile = useCallback(async (input: ProfileInput): Promise<boolean> => {
    if (!session) return false;
    const { controller, generation } = begin();
    setStatus("working");
    try {
      const user = await authApi.updateProfile(input, controller.signal);
      if (!current(generation, controller)) return false;
      setSession((active) => active ? { ...active, user } : active);
      setStatus("authenticated");
      setLiveStatus("Profile updated.");
      return true;
    } catch (requestError) {
      if (!current(generation, controller) || isAbortError(requestError)) return false;
      const nextError = toIdentityError(requestError);
      if (isAuthenticationRequired(nextError)) {
        clearCachedSession(nextError.message, nextError);
        return false;
      }
      setStatus("authenticated");
      setError(nextError);
      setLiveStatus(nextError.message);
      return false;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [begin, clearCachedSession, current, session]);

  const logout = useCallback(async (): Promise<boolean> => {
    const { controller, generation } = begin();
    setStatus("working");
    try {
      await authApi.logout(controller.signal);
      if (!current(generation, controller)) return false;
      setSession(null);
      setStatus("guest");
      setLiveStatus("Signed out from this browser.");
      return true;
    } catch (requestError) {
      if (!current(generation, controller) || isAbortError(requestError)) return false;
      const nextError = toIdentityError(requestError);
      if (isAuthenticationRequired(nextError)) {
        clearCachedSession("The local session was already inactive.");
        return true;
      }
      setStatus(session ? "authenticated" : "guest");
      setError(nextError);
      setLiveStatus(nextError.message);
      return false;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [begin, clearCachedSession, current, session]);

  const value = useMemo<IdentityContextValue>(() => ({
    session,
    status,
    error,
    liveStatus,
    login,
    signup,
    logout,
    refreshSession,
    updateProfile,
    changePassword,
    invalidateSession,
    invalidateCommunityAccess,
    clearError: () => setError(null),
    announce: setLiveStatus,
  }), [session, status, error, liveStatus, login, signup, logout, refreshSession, updateProfile, changePassword, invalidateSession, invalidateCommunityAccess]);

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): IdentityContextValue {
  const value = useContext(IdentityContext);
  if (!value) throw new Error("useIdentity must be used inside IdentityProvider");
  return value;
}
