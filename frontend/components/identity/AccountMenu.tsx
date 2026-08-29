"use client";

import { CaretDown, GearSix, SignIn, SignOut, UserPlus, UsersThree } from "@phosphor-icons/react";
import { Avatar, Button, DropdownMenu } from "@radix-ui/themes";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useIdentity } from "../../lib/identity-context";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "A";
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
}

export default function AccountMenu() {
  const router = useRouter();
  const identity = useIdentity();
  const user = identity.session?.user;

  if (!user) {
    return (
      <DropdownMenu.Root>
        <DropdownMenu.Trigger>
          <Button aria-label="Open guest account menu" className="identity-account-trigger" size="2" variant="soft">
            <SignIn aria-hidden="true" size={18} weight="duotone" />
            <span className="identity-account-label">Account</span>
            <CaretDown aria-hidden="true" size={14} weight="bold" />
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Content align="end" className="identity-account-menu" size="2">
          <DropdownMenu.Label><span className="identity-menu-name">Guest access</span></DropdownMenu.Label>
          <DropdownMenu.Item asChild><Link href="/login"><SignIn aria-hidden="true" size={17} /> Sign in</Link></DropdownMenu.Item>
          <DropdownMenu.Item asChild><Link href="/signup"><UserPlus aria-hidden="true" size={17} /> Create account</Link></DropdownMenu.Item>
          <DropdownMenu.Separator />
          <DropdownMenu.Item asChild><Link href="/settings"><GearSix aria-hidden="true" size={17} /> Settings and appearance</Link></DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Root>
    );
  }

  const label = user.display_name ?? user.username;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger>
        <Button aria-label={`Open account menu for ${label}`} className="identity-account-trigger" size="2" variant="soft">
          <Avatar alt="" aria-hidden="true" fallback={initials(label)} radius="full" size="1" src={user.avatar_url ?? undefined} />
          <span className="identity-account-label">{label}</span>
          <CaretDown aria-hidden="true" size={14} weight="bold" />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content align="end" className="identity-account-menu" size="2">
        <DropdownMenu.Label>
          <span className="identity-menu-name">{label}</span>
          <span className="identity-menu-username">@{user.username}</span>
        </DropdownMenu.Label>
        <DropdownMenu.Separator />
        <DropdownMenu.Item asChild><Link href="/communities"><UsersThree aria-hidden="true" size={17} /> Collaboration spaces</Link></DropdownMenu.Item>
        <DropdownMenu.Item asChild><Link href="/settings"><GearSix aria-hidden="true" size={17} /> Settings</Link></DropdownMenu.Item>
        <DropdownMenu.Separator />
        <DropdownMenu.Item
          color="red"
          disabled={identity.status === "working"}
          onSelect={(event) => {
            event.preventDefault();
            void identity.logout().then((didLogout) => {
              if (didLogout) router.push("/");
            });
          }}
        >
          <SignOut aria-hidden="true" size={17} /> Sign out
        </DropdownMenu.Item>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}
