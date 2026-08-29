"use client";

import { ArrowRight, LockKey, ShieldCheck, UserPlus } from "@phosphor-icons/react";
import { Button } from "@radix-ui/themes";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useIdentity } from "../../lib/identity-context";

type AuthMode = "login" | "signup";

export default function AuthEntry({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const identity = useIdentity();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loginIdentity, setLoginIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const isSignup = mode === "signup";
  const isWorking = identity.status === "working";

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    identity.clearError();
    setLocalError("");

    if (isSignup && password.length < 12) {
      setLocalError("Use at least 12 characters for your password.");
      identity.announce("The password needs at least 12 characters.");
      return;
    }

    const submittedPassword = password;
    setPassword("");
    const succeeded = isSignup
      ? await identity.signup({
          username: username.trim(),
          email: email.trim() || null,
          password: submittedPassword,
          display_name: displayName.trim() || null,
        })
      : await identity.login({ identity: loginIdentity.trim(), password: submittedPassword });

    if (succeeded) router.push("/communities");
  };

  if (identity.status === "bootstrapping") {
    return (
      <section aria-busy="true" aria-labelledby="auth-loading-title" className="auth-entry auth-entry-loading">
        <LockKey aria-hidden="true" size={28} weight="duotone" />
        <h1 id="auth-loading-title">Checking your session</h1>
        <p>The planning demo remains available while account access is checked.</p>
      </section>
    );
  }

  if (identity.session) {
    return (
      <section aria-labelledby="auth-ready-title" className="auth-entry auth-entry-ready">
        <ShieldCheck aria-hidden="true" size={30} weight="duotone" />
        <h1 id="auth-ready-title">You are signed in</h1>
        <p>Continue to your collaboration spaces or return to the separate planning demo.</p>
        <div className="auth-ready-actions">
          <Button asChild size="3"><Link href="/communities">Open collaboration spaces <ArrowRight aria-hidden="true" size={17} /></Link></Button>
          <Button asChild size="3" variant="outline"><Link href="/">Open planning demo</Link></Button>
        </div>
      </section>
    );
  }

  const error = localError || identity.error?.message;

  return (
    <section aria-labelledby="auth-title" className="auth-entry">
      <div className="auth-heading">
        {isSignup ? <UserPlus aria-hidden="true" size={26} weight="duotone" /> : <LockKey aria-hidden="true" size={26} weight="duotone" />}
        <h1 id="auth-title">{isSignup ? "Create your account" : "Sign in to collaborate"}</h1>
        <p>{isSignup ? "Create a local account for collaboration spaces." : "Use your username or email to open collaboration spaces."}</p>
      </div>

      <form className="auth-form" onSubmit={submit}>
        {isSignup ? (
          <>
            <div className="auth-field">
              <label htmlFor="auth-username">Username</label>
              <input aria-describedby="auth-username-help" autoComplete="username" id="auth-username" maxLength={64} minLength={3} onChange={(event) => setUsername(event.target.value)} required type="text" value={username} />
              <span id="auth-username-help">3-64 characters using letters, numbers, dots, underscores or hyphens.</span>
            </div>
            <div className="auth-field">
              <label htmlFor="auth-email">Email <span>(optional)</span></label>
              <input autoComplete="email" id="auth-email" maxLength={254} onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
            </div>
            <div className="auth-field">
              <label htmlFor="auth-display-name">Display name <span>(optional)</span></label>
              <input autoComplete="name" id="auth-display-name" maxLength={120} onChange={(event) => setDisplayName(event.target.value)} type="text" value={displayName} />
            </div>
          </>
        ) : (
          <div className="auth-field">
            <label htmlFor="auth-identity">Username or email</label>
            <input autoComplete="username" id="auth-identity" maxLength={254} minLength={3} onChange={(event) => setLoginIdentity(event.target.value)} required type="text" value={loginIdentity} />
          </div>
        )}

        <div className="auth-field">
          <label htmlFor="auth-password">Password</label>
          <input
            aria-describedby={isSignup ? "auth-password-help" : undefined}
            autoComplete={isSignup ? "new-password" : "current-password"}
            id="auth-password"
            maxLength={128}
            minLength={isSignup ? 12 : 1}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {isSignup ? <span id="auth-password-help">Use 12-128 characters and at least three of: lowercase, uppercase, number and symbol.</span> : null}
        </div>

        {error ? <div aria-live="assertive" className="auth-error" role="alert"><strong>{identity.error?.code ?? "CHECK_DETAILS"}</strong><span>{error}</span></div> : null}

        <Button className="auth-submit" disabled={isWorking} size="3" type="submit">
          {isWorking ? "Please wait" : isSignup ? "Create account" : "Sign in"}
          {!isWorking ? <ArrowRight aria-hidden="true" size={17} /> : null}
        </Button>
      </form>

      <div className="auth-alternatives">
        <p>{isSignup ? "Already have an account?" : "Need an account?"} <Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create one"}</Link></p>
        <Link className="auth-guest-link" href="/">Continue to the planning demo as a guest</Link>
      </div>
      <p className="auth-privacy-note">Session cookies are HttpOnly. This interface never reads or stores the session token.</p>
    </section>
  );
}
