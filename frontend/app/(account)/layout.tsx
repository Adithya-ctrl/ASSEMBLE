import type { ReactNode } from "react";

import IdentityShell from "../../components/identity/IdentityShell";

export default function AccountLayout({ children }: { children: ReactNode }) {
  return <IdentityShell>{children}</IdentityShell>;
}
