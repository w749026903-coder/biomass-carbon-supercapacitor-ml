$ErrorActionPreference = 'Stop'
$taskArchiveManifest = Get-Content -LiteralPath 'D:\机器学习-超级电容器\文献更新_2023至今\新增归档清单.json' -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($taskEntry in $taskArchiveManifest) {
    $taskSource = [System.IO.Path]::GetFullPath($taskEntry.source)
    $taskTarget = [System.IO.Path]::GetFullPath($taskEntry.target)
    if (-not $taskSource.StartsWith('D:\机器学习-超级电容器\文献更新_2023至今\', [System.StringComparison]::OrdinalIgnoreCase) -or -not $taskTarget.StartsWith('D:\文献\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Archive target out of scope' }
    if (Test-Path -LiteralPath $taskTarget) { throw "Archive target already exists: $taskTarget" }
    if ((Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw 'Source hash mismatch' }
}
foreach ($taskEntry in $taskArchiveManifest) {
    $taskTargetParent = [System.IO.Path]::GetDirectoryName($taskEntry.target)
    if (-not (Test-Path -LiteralPath $taskTargetParent -PathType Container)) { [System.IO.Directory]::CreateDirectory($taskTargetParent) | Out-Null }
    [System.IO.File]::Copy($taskEntry.source, $taskEntry.target, $false)
    if ((Get-FileHash -LiteralPath $taskEntry.target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.sha256) { throw 'Archive hash mismatch' }
}
Write-Output "Archived and verified $($taskArchiveManifest.Count) new files."
