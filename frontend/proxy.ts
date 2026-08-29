import { NextResponse, type NextRequest } from "next/server";

const PROOF_PREFIX = "/initiatives/";
const PROOF_SUFFIX = "/proof";

export function proxy(request: NextRequest) {
  const pathname = new URL(request.url).pathname;
  if (!pathname.startsWith(PROOF_PREFIX) || !pathname.endsWith(PROOF_SUFFIX)) {
    return NextResponse.next();
  }

  const encodedInitiativeId = pathname.slice(PROOF_PREFIX.length, -PROOF_SUFFIX.length);
  try {
    decodeURIComponent(encodedInitiativeId);
    return NextResponse.next();
  } catch {
    const safeUrl = request.nextUrl.clone();
    safeUrl.pathname = `${PROOF_PREFIX}__MALFORMED_INITIATIVE_ID__${PROOF_SUFFIX}`;
    return NextResponse.rewrite(safeUrl);
  }
}

export const config = {
  matcher: "/initiatives/:path*",
};
