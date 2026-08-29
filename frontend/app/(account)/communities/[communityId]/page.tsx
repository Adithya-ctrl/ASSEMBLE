import CommunityAdminPanel from "../../../../components/community-admin/CommunityAdminPanel";

export default async function CommunityDetailPage({ params }: { params: Promise<{ communityId: string }> }) {
  const { communityId } = await params;
  return <CommunityAdminPanel communityId={communityId} />;
}
