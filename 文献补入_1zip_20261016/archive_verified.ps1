$ErrorActionPreference = 'Stop'
$taskManifest = Get-Content -LiteralPath 'D:\机器学习-超级电容器\文献补入_1zip_20261016\归档清单_17篇.json' -Raw -Encoding utf8 | ConvertFrom-Json
if ($taskManifest.Count -ne 17) { throw 'Unexpected archive file count' }
foreach ($taskEntry in $taskManifest) {
    $taskSource = [System.IO.Path]::GetFullPath($taskEntry.source)
    $taskTarget = [System.IO.Path]::GetFullPath($taskEntry.target)
    if (-not $taskSource.StartsWith('D:\机器学习-超级电容器\文献补入_1zip_20261016\已核验PDF暂存\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Source outside staging scope' }
    if ([System.IO.Path]::GetDirectoryName($taskTarget) -ne 'D:\文献') { throw 'Target outside literature directory' }
    if (Test-Path -LiteralPath $taskTarget) { throw "Target exists: $taskTarget" }
    if ((Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw 'Source hash mismatch' }
}
foreach ($taskEntry in $taskManifest) {
    [System.IO.File]::Copy($taskEntry.source, $taskEntry.target, $false)
    if ((Get-FileHash -LiteralPath $taskEntry.target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw 'Target hash mismatch' }
}
Write-Output 'Archived 17 verified new PDFs; original ZIP and existing PDFs preserved.'
