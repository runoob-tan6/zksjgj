[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "dist"),
    [string]$WorkDirectory = (Join-Path $PSScriptRoot "build")
)

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$SpecFile = Join-Path $ProjectDir "borehole_v4.spec"
$UvPath = Join-Path $HOME ".local\bin\uv.exe"
$TargetExe = Join-Path $OutputDirectory "钻孔数据编辑工具v4.0.exe"

if (-not (Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
    throw "找不到 spec 文件：$SpecFile"
}

if (-not (Test-Path -LiteralPath $UvPath -PathType Leaf)) {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $uvCommand) {
        throw "找不到 uv.exe。请安装 uv，或将 uv.exe 加入 PATH。"
    }
    $UvPath = $uvCommand.Source
}

if (Test-Path -LiteralPath $TargetExe -PathType Leaf) {
    $targetFullPath = [IO.Path]::GetFullPath($TargetExe)
    $runningProcesses = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            try {
                $_.Path -and ([IO.Path]::GetFullPath($_.Path) -ieq $targetFullPath)
            }
            catch {
                $false
            }
        }

    if ($runningProcesses) {
        $ids = ($runningProcesses.Id -join ", ")
        throw "目标 exe 正在运行，进程 ID：$ids。请先关闭它：$TargetExe"
    }
}

Write-Host "使用项目虚拟环境开始打包..."
Write-Host "项目目录：$ProjectDir"
Write-Host "Python 环境由 uv 根据 pyproject.toml 管理。"

& $UvPath run `
    --project $ProjectDir `
    --extra dev `
    python -m PyInstaller `
    --clean `
    --noconfirm `
    --distpath $OutputDirectory `
    --workpath $WorkDirectory `
    $SpecFile

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败，退出码：$LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $TargetExe -PathType Leaf)) {
    throw "PyInstaller 返回成功，但没有找到目标 exe：$TargetExe"
}

$result = Get-Item -LiteralPath $TargetExe
Write-Host ""
Write-Host "打包完成：$($result.FullName)"
Write-Host "文件大小：$([Math]::Round($result.Length / 1MB, 2)) MB"
Write-Host "修改时间：$($result.LastWriteTime)"
