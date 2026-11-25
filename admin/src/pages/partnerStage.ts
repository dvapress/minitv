import { getLocale, type Locale } from "../i18n";

/** Supplier-facing lifecycle label. Approved ≠ live, so the tag must say so. */
export function partnerStage(
  status: string,
  reviewState: string,
  locale: Locale = getLocale()
): string {
  const zh = locale === "zh";
  if (reviewState === "rejected") return zh ? "已驳回" : "Rejected";
  if (reviewState === "pending") return zh ? "审核中" : "In Review";
  if (status === "published") return zh ? "已上架" : "Published";
  if (status === "unpublished") return zh ? "已下架" : "Unpublished";
  if (reviewState === "approved") return zh ? "待上架" : "Approved";
  return zh ? "草稿" : "Draft";
}

export function partnerStageColor(status: string, reviewState: string): string | undefined {
  if (reviewState === "rejected") return "red";
  if (reviewState === "pending") return "orange";
  if (status === "published") return "green";
  if (reviewState === "approved") return "blue";
  return undefined;
}
