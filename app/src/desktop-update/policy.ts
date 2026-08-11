export interface InstallPolicy {
  readonly canInstallInApp: boolean;
  readonly packageLabel: string;
}

export function installPolicy(
  bundleType: string | null | undefined,
): InstallPolicy {
  if (bundleType === "app") {
    return { canInstallInApp: true, packageLabel: "macOS app" };
  }
  return {
    canInstallInApp: false,
    packageLabel: bundleType === null || bundleType === undefined
      ? "unknown package"
      : String(bundleType),
  };
}
