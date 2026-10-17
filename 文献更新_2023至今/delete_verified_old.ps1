$ErrorActionPreference = 'Stop'
$taskManifestPath = 'D:\机器学习-超级电容器\文献更新_2023至今\删除清单_2022年及以前.json'
$taskLogPath = 'D:\机器学习-超级电容器\文献更新_2023至今\删除执行日志.jsonl'
$taskManifest = Get-Content -LiteralPath $taskManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($taskManifest.Count -ne 47) { throw 'Unexpected deletion manifest size' }
Add-Type -AssemblyName Microsoft.VisualBasic
foreach ($taskEntry in $taskManifest) {
    $taskResolvedPath = [System.IO.Path]::GetFullPath($taskEntry.path)
    $taskInScope = $taskResolvedPath.StartsWith('D:\文献\', [System.StringComparison]::OrdinalIgnoreCase) -or $taskResolvedPath.StartsWith('D:\机器学习-超级电容器\', [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $taskInScope -or $taskEntry.year -ge 2023 -or $taskEntry.year -lt 1900) { throw "Out of scope: $taskResolvedPath" }
    if (-not (Test-Path -LiteralPath $taskResolvedPath -PathType Leaf)) { throw "Missing target: $taskResolvedPath" }
    $taskActualHash = (Get-FileHash -LiteralPath $taskResolvedPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskActualHash -ne $taskEntry.sha256) { throw "Hash changed: $taskResolvedPath" }
}
foreach ($taskEntry in $taskManifest) {
    $taskResolvedPath = [System.IO.Path]::GetFullPath($taskEntry.path)
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($taskResolvedPath, [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
    if (Test-Path -LiteralPath $taskResolvedPath) { throw "Deletion did not complete: $taskResolvedPath" }
    [pscustomobject]@{ path=$taskResolvedPath; doi=$taskEntry.doi; year=$taskEntry.year; sha256=$taskEntry.sha256; status='moved_to_recycle_bin'; time=(Get-Date -Format o) } | ConvertTo-Json -Compress | Add-Content -LiteralPath $taskLogPath -Encoding utf8
}
Write-Output "Moved $($taskManifest.Count) verified old files to Recycle Bin."
