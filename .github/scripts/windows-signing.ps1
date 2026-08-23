param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Import', 'Verify', 'Cleanup')]
    [string]$Action,
    [string]$ConfigPath,
    [string]$ReceiptPath,
    [string]$PfxPath,
    [string]$ReleaseRoot,
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Require-PathArgument([string]$Name, [string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required for $Action"
    }
}

function Remove-ImportedCertificates([object[]]$Certificates) {
    foreach ($certificate in $Certificates) {
        $path = "Cert:\CurrentUser\My\$($certificate.Thumbprint)"
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

switch ($Action) {
    'Import' {
        Require-PathArgument 'ConfigPath' $ConfigPath
        Require-PathArgument 'ReceiptPath' $ReceiptPath
        Require-PathArgument 'PfxPath' $PfxPath
        if ([string]::IsNullOrWhiteSpace($env:WINDOWS_CERTIFICATE_PFX_BASE64) -or
            [string]::IsNullOrWhiteSpace($env:WINDOWS_CERTIFICATE_PASSWORD)) {
            throw 'Windows Authenticode credentials are incomplete'
        }
        $imported = @()
        try {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PfxPath) |
                Out-Null
            $bytes = [Convert]::FromBase64String(
                $env:WINDOWS_CERTIFICATE_PFX_BASE64)
            [IO.File]::WriteAllBytes($PfxPath, $bytes)
            $password = ConvertTo-SecureString `
                -String $env:WINDOWS_CERTIFICATE_PASSWORD `
                -AsPlainText `
                -Force
            $imported = @(
                Import-PfxCertificate `
                    -FilePath $PfxPath `
                    -CertStoreLocation 'Cert:\CurrentUser\My' `
                    -Password $password `
                    -Exportable:$false
            )
            if ($imported.Count -eq 0) {
                throw 'The PFX imported no certificates'
            }
            $receipt = [ordered]@{
                schema = 'atpiano.windows-signing-receipt.v1'
                importedThumbprints = @($imported | ForEach-Object Thumbprint)
            }
            [IO.File]::WriteAllText(
                $ReceiptPath,
                (($receipt | ConvertTo-Json -Depth 4) + "`n"),
                [Text.UTF8Encoding]::new($false))
            $codeSigningOid = '1.3.6.1.5.5.7.3.3'
            $signers = @(
                $imported | Where-Object {
                    $_.HasPrivateKey -and
                    @($_.EnhancedKeyUsageList | ForEach-Object {
                        $_.ObjectId.Value
                    }) -contains $codeSigningOid
                }
            )
            if ($signers.Count -ne 1) {
                throw "Expected one private code-signing certificate; found $($signers.Count)"
            }
            $signer = $signers[0]
            $now = Get-Date
            if ($signer.NotBefore -gt $now -or $signer.NotAfter -le $now) {
                throw 'The code-signing certificate is outside its validity period'
            }
            if ($signer.Subject -eq $signer.Issuer) {
                throw 'A self-signed certificate is forbidden for public releases'
            }
            $config = [ordered]@{
                bundle = [ordered]@{
                    windows = [ordered]@{
                        certificateThumbprint = $signer.Thumbprint
                        digestAlgorithm = 'sha256'
                        timestampUrl = 'http://timestamp.digicert.com'
                        tsp = $true
                    }
                }
            }
            [IO.File]::WriteAllText(
                $ConfigPath,
                (($config | ConvertTo-Json -Depth 6) + "`n"),
                [Text.UTF8Encoding]::new($false))
            $receipt.signerThumbprint = $signer.Thumbprint
            $receipt.signerSubject = $signer.Subject
            $receipt.notAfter = $signer.NotAfter.ToUniversalTime().ToString('o')
            [IO.File]::WriteAllText(
                $ReceiptPath,
                (($receipt | ConvertTo-Json -Depth 4) + "`n"),
                [Text.UTF8Encoding]::new($false))
            Write-Output (
                'Imported Windows code-signing certificate: subject={0}; ' +
                'thumbprint={1}; expires={2:o}' -f
                $signer.Subject, $signer.Thumbprint, $signer.NotAfter.ToUniversalTime())
        }
        catch {
            Remove-ImportedCertificates $imported
            Remove-Item -LiteralPath $ConfigPath -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $ReceiptPath -Force -ErrorAction SilentlyContinue
            throw
        }
        finally {
            $bytes = $null
            $password = $null
            Remove-Item -LiteralPath $PfxPath -Force -ErrorAction SilentlyContinue
        }
    }
    'Verify' {
        Require-PathArgument 'ReceiptPath' $ReceiptPath
        Require-PathArgument 'ReleaseRoot' $ReleaseRoot
        Require-PathArgument 'ReportPath' $ReportPath
        $receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
        $applications = @(
            Get-ChildItem -LiteralPath $ReleaseRoot -Filter 'atpiano-desktop.exe' -File
        )
        $installers = @(
            Get-ChildItem `
                -LiteralPath (Join-Path $ReleaseRoot 'bundle\nsis') `
                -Filter 'Atpiano_*_x64-setup.exe' `
                -File
        )
        $updaters = @(
            Get-ChildItem `
                -LiteralPath (Join-Path $ReleaseRoot 'bundle\nsis') `
                -Filter 'Atpiano_*_x64-setup.nsis.zip' `
                -File
        )
        if ($applications.Count -ne 1 -or $installers.Count -ne 1 -or
            $updaters.Count -ne 1) {
            throw 'Expected one signed app, NSIS installer, and NSIS updater archive'
        }
        $records = @()
        foreach ($file in @($applications[0], $installers[0])) {
            $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
            if ($signature.Status -ne 'Valid') {
                throw "$($file.Name) Authenticode status is $($signature.Status)"
            }
            if ($signature.SignerCertificate.Thumbprint -ne
                $receipt.signerThumbprint) {
                throw "$($file.Name) was signed by an unexpected certificate"
            }
            if ($null -eq $signature.TimeStamperCertificate) {
                throw "$($file.Name) has no trusted timestamp"
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
        $signaturePath = "$($updaters[0].FullName).sig"
        if (-not (Test-Path -LiteralPath $signaturePath) -or
            (Get-Item -LiteralPath $signaturePath).Length -lt 32) {
            throw 'The Windows updater detached signature is missing or empty'
        }
        $forbidden = @(
            Get-ChildItem `
                -LiteralPath (Join-Path $env:GITHUB_WORKSPACE `
                    'app\src-tauri\resources\desktop-runtime') `
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
            signerSubject = $receipt.signerSubject
            signerThumbprint = $receipt.signerThumbprint
            signedFiles = $records
            updater = [ordered]@{
                name = $updaters[0].Name
                bytes = $updaters[0].Length
                sha256 = (Get-FileHash -LiteralPath $updaters[0].FullName `
                    -Algorithm SHA256).Hash.ToLowerInvariant()
                signatureBytes = (Get-Item -LiteralPath $signaturePath).Length
            }
            forbiddenScoreAssetCount = $forbidden.Count
        }
        [IO.File]::WriteAllText(
            $ReportPath,
            (($report | ConvertTo-Json -Depth 8) + "`n"),
            [Text.UTF8Encoding]::new($false))
        Write-Output 'Verified signed and timestamped Windows desktop artifacts'
    }
    'Cleanup' {
        Require-PathArgument 'ConfigPath' $ConfigPath
        Require-PathArgument 'ReceiptPath' $ReceiptPath
        Require-PathArgument 'PfxPath' $PfxPath
        if (Test-Path -LiteralPath $ReceiptPath) {
            $receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
            $certificates = @(
                $receipt.importedThumbprints | ForEach-Object {
                    [pscustomobject]@{ Thumbprint = $_ }
                }
            )
            Remove-ImportedCertificates $certificates
        }
        Remove-Item -LiteralPath $PfxPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $ConfigPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $ReceiptPath -Force -ErrorAction SilentlyContinue
        Write-Output 'Removed temporary Windows signing material'
    }
}
