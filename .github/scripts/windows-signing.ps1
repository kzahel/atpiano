param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseRoot,
    [Parameter(Mandatory = $true)]
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$applications = @(
    Get-ChildItem -LiteralPath $ReleaseRoot `
        -Filter 'atpiano-desktop.exe' -File
)
$installers = @(
    Get-ChildItem `
        -LiteralPath (Join-Path $ReleaseRoot 'bundle\nsis') `
        -Filter 'Atpiano_*_x64-setup.exe' `
        -File
)
if ($applications.Count -ne 1 -or $installers.Count -ne 1) {
    throw 'Expected one signed app and one signed NSIS installer'
}

$records = @()
$signerSubject = $null
foreach ($file in @($applications[0], $installers[0])) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid') {
        throw "$($file.Name) Authenticode status is $($signature.Status)"
    }
    if ($signature.SignerCertificate.Subject -notmatch
        'CN=Kyle Graehl(?:,|$)') {
        throw "$($file.Name) has unexpected signer $($signature.SignerCertificate.Subject)"
    }
    if ($null -eq $signature.TimeStamperCertificate) {
        throw "$($file.Name) has no trusted timestamp"
    }
    if ($null -eq $signerSubject) {
        $signerSubject = $signature.SignerCertificate.Subject
    }
    elseif ($signature.SignerCertificate.Subject -ne $signerSubject) {
        throw "$($file.Name) was signed by a different publisher"
    }
    $records += [ordered]@{
        name = $file.Name
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName `
            -Algorithm SHA256).Hash.ToLowerInvariant()
        signerThumbprint = $signature.SignerCertificate.Thumbprint
        timestampSubject = $signature.TimeStamperCertificate.Subject
    }
}

$signaturePath = "$($installers[0].FullName).sig"
if (-not (Test-Path -LiteralPath $signaturePath) -or
    (Get-Item -LiteralPath $signaturePath).Length -lt 32) {
    throw 'The Windows updater detached signature is missing or empty'
}
$resourceRoot = Join-Path $env:GITHUB_WORKSPACE `
    'app\src-tauri\resources\desktop-runtime'
$forbidden = @(
    Get-ChildItem `
        -LiteralPath $resourceRoot `
        -Recurse `
        -Force `
        -ErrorAction Stop |
        Where-Object {
            $_.Name -in @('MIDI2ScoreTF.ckpt', 'MIDI2ScoreTransformer',
                'score-runtime')
        }
)
if ($forbidden.Count -ne 0) {
    throw 'The packaged Windows resource tree contains a forbidden score model asset'
}

$report = [ordered]@{
    schema = 'atpiano.windows-package-signing-audit.v1'
    status = 'passed'
    signingProvider = 'Azure Trusted Signing'
    signerSubject = $signerSubject
    signerThumbprints = @($records | ForEach-Object {
            $_.signerThumbprint
        } | Sort-Object -Unique)
    signedFiles = $records
    updater = [ordered]@{
        name = $installers[0].Name
        bytes = $installers[0].Length
        sha256 = (Get-FileHash -LiteralPath $installers[0].FullName `
            -Algorithm SHA256).Hash.ToLowerInvariant()
        signatureBytes = (Get-Item -LiteralPath $signaturePath).Length
    }
    forbiddenScoreAssetCount = $forbidden.Count
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ReportPath) |
    Out-Null
[IO.File]::WriteAllText(
    $ReportPath,
    (($report | ConvertTo-Json -Depth 8) + "`n"),
    [Text.UTF8Encoding]::new($false))
Write-Output 'Verified signed and timestamped Windows desktop artifacts'
