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
  if (bundleType === "nsis") {
    return { canInstallInApp: true, packageLabel: "Windows setup" };
  }
  return {
    canInstallInApp: false,
    packageLabel: bundleType === null || bundleType === undefined
      ? "unknown package"
      : String(bundleType),
  };
}
