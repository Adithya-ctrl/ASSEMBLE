"use client";

import { Info, LockKey, Palette, SignIn, UserCircle } from "@phosphor-icons/react";
import { Button, Tabs } from "@radix-ui/themes";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { useIdentity } from "../../lib/identity-context";
import { useAssembly } from "../../lib/workflow-context";

function AppearanceSettings() {
  const workflow = useAssembly();
  const { preferences } = workflow;

  return (
    <div className="settings-appearance">
      <fieldset>
        <legend>Theme</legend>
        {(["system", "light", "dark"] as const).map((theme) => (
          <label key={theme}><input checked={preferences.theme === theme} name="settings-theme" onChange={() => workflow.updatePreferences({ theme })} type="radio" /> {theme === "system" ? "Use device setting" : `${theme.charAt(0).toUpperCase()}${theme.slice(1)} theme`}</label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Contrast</legend>
        <label><input checked={preferences.contrast === "standard"} name="settings-contrast" onChange={() => workflow.updatePreferences({ contrast: "standard" })} type="radio" /> Standard contrast</label>
        <label><input checked={preferences.contrast === "high"} name="settings-contrast" onChange={() => workflow.updatePreferences({ contrast: "high" })} type="radio" /> High contrast</label>
      </fieldset>
      <fieldset>
        <legend>Motion</legend>
        <label><input checked={preferences.motion === "system"} name="settings-motion" onChange={() => workflow.updatePreferences({ motion: "system" })} type="radio" /> Follow device preference</label>
        <label><input checked={preferences.motion === "reduced"} name="settings-motion" onChange={() => workflow.updatePreferences({ motion: "reduced" })} type="radio" /> Reduce non-essential motion</label>
      </fieldset>
      <fieldset>
        <legend>Planning demo community view</legend>
        <label><input checked={preferences.inventoryView === "graph"} name="settings-community-view" onChange={() => workflow.updatePreferences({ inventoryView: "graph" })} type="radio" /> Graph view</label>
        <label><input checked={preferences.inventoryView === "list"} name="settings-community-view" onChange={() => workflow.updatePreferences({ inventoryView: "list" })} type="radio" /> List view</label>
      </fieldset>
      <div className="settings-note"><Info aria-hidden="true" size={18} weight="duotone" /><p>Only these four appearance preferences are stored in the versioned ASSEMBLE UI preference cookie. Account and security data are excluded.</p></div>
    </div>
  );
}

function AccountSettings() {
  const identity = useIdentity();
  const user = identity.session?.user;
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? "");

  if (!user) return null;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await identity.updateProfile({ display_name: displayName.trim() || null, avatar_url: avatarUrl.trim() || null });
  };

  return (
    <form className="settings-form" onSubmit={submit}>
      <div className="settings-account-summary"><UserCircle aria-hidden="true" size={25} weight="duotone" /><div><strong>{user.display_name ?? user.username}</strong><span>@{user.username}{user.email ? `, ${user.email}` : ""}</span></div></div>
      <div className="settings-field"><label htmlFor="settings-display-name">Display name</label><input id="settings-display-name" maxLength={120} onChange={(event) => setDisplayName(event.target.value)} type="text" value={displayName} /><span>Leave blank to use your username.</span></div>
      <div className="settings-field"><label htmlFor="settings-avatar-url">Avatar URL</label><input id="settings-avatar-url" maxLength={512} onChange={(event) => setAvatarUrl(event.target.value)} placeholder="https://example.org/avatar.jpg" type="url" value={avatarUrl} /><span>Optional. HTTPS URLs only. ASSEMBLE stores the URL, not the image.</span></div>
      {identity.error ? <div className="settings-error" role="alert"><strong>{identity.error.code}</strong><span>{identity.error.message}</span></div> : null}
      <Button className="settings-submit" disabled={identity.status === "working"} size="3" type="submit">{identity.status === "working" ? "Saving" : "Save profile"}</Button>
    </form>
  );
}

function SecuritySettings() {
  const identity = useIdentity();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError("");
    if (newPassword !== confirmPassword) {
      setLocalError("The new passwords do not match.");
      identity.announce("The new passwords do not match.");
      return;
    }
    if (newPassword.length < 12) {
      setLocalError("Use at least 12 characters for the new password.");
      identity.announce("The new password needs at least 12 characters.");
      return;
    }
    const succeeded = await identity.changePassword({ current_password: currentPassword, new_password: newPassword });
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    if (succeeded) identity.announce("Password changed. Other sessions were signed out.");
  };

  return (
    <form className="settings-form" onSubmit={submit}>
      <div className="settings-security-intro"><LockKey aria-hidden="true" size={24} weight="duotone" /><p>Changing your password signs out every other session and refreshes this one.</p></div>
      <div className="settings-field"><label htmlFor="settings-current-password">Current password</label><input autoComplete="current-password" id="settings-current-password" maxLength={128} onChange={(event) => setCurrentPassword(event.target.value)} required type="password" value={currentPassword} /></div>
      <div className="settings-field"><label htmlFor="settings-new-password">New password</label><input aria-describedby="settings-password-help" autoComplete="new-password" id="settings-new-password" maxLength={128} minLength={12} onChange={(event) => setNewPassword(event.target.value)} required type="password" value={newPassword} /><span id="settings-password-help">Use 12-128 characters and at least three of: lowercase, uppercase, number and symbol.</span></div>
      <div className="settings-field"><label htmlFor="settings-confirm-password">Confirm new password</label><input autoComplete="new-password" id="settings-confirm-password" maxLength={128} minLength={12} onChange={(event) => setConfirmPassword(event.target.value)} required type="password" value={confirmPassword} /></div>
      {localError || identity.error ? <div className="settings-error" role="alert"><strong>{identity.error?.code ?? "CHECK_PASSWORDS"}</strong><span>{localError || identity.error?.message}</span></div> : null}
      <Button className="settings-submit" disabled={identity.status === "working"} size="3" type="submit">{identity.status === "working" ? "Changing password" : "Change password"}</Button>
    </form>
  );
}

export default function SettingsPanel() {
  const identity = useIdentity();

  if (identity.status === "bootstrapping") return <section aria-busy="true" className="settings-panel"><h1>Settings</h1><p>Checking account access.</p></section>;

  if (!identity.session) {
    return (
      <section aria-labelledby="settings-title" className="settings-panel">
        <div className="settings-heading"><div><h1 id="settings-title">Settings</h1><p>Appearance works for guests and signed-in collaborators.</p></div><Button asChild size="3"><Link href="/login"><SignIn aria-hidden="true" size={17} /> Sign in for account settings</Link></Button></div>
        <section aria-labelledby="settings-appearance-title" className="settings-guest-appearance"><div className="settings-section-heading"><Palette aria-hidden="true" size={23} weight="duotone" /><h2 id="settings-appearance-title">Appearance</h2></div><AppearanceSettings /></section>
      </section>
    );
  }

  return (
    <section aria-labelledby="settings-title" className="settings-panel">
      <div className="settings-heading"><div><h1 id="settings-title">Settings</h1><p>Manage your profile, password and the allow-listed appearance preferences.</p></div></div>
      <Tabs.Root className="settings-tabs" defaultValue="account" onValueChange={(value) => identity.announce(`${value.charAt(0).toUpperCase()}${value.slice(1)} settings selected.`)}>
        <Tabs.List aria-label="Settings sections" className="settings-tab-list">
          <Tabs.Trigger value="account"><UserCircle aria-hidden="true" size={17} /> Account</Tabs.Trigger>
          <Tabs.Trigger value="security"><LockKey aria-hidden="true" size={17} /> Security</Tabs.Trigger>
          <Tabs.Trigger value="appearance"><Palette aria-hidden="true" size={17} /> Appearance</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content className="settings-tab-content" value="account"><AccountSettings /></Tabs.Content>
        <Tabs.Content className="settings-tab-content" value="security"><SecuritySettings /></Tabs.Content>
        <Tabs.Content className="settings-tab-content" value="appearance"><AppearanceSettings /></Tabs.Content>
      </Tabs.Root>
    </section>
  );
}
