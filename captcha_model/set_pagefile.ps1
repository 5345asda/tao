# 设置 Windows 虚拟内存（页面文件）
# 需要管理员权限运行

Write-Host "正在设置页面文件..." -ForegroundColor Green

# 设置 C 盘页面文件：初始 16GB，最大 32GB
try {
    $pageFile = Get-WmiObject -Query "SELECT * FROM Win32_PageFileSetting WHERE Name='C:\\pagefile.sys'"

    if ($pageFile) {
        $pageFile.InitialSize = 16384
        $pageFile.MaximumSize = 32768
        $pageFile.Put() | Out-Null
        Write-Host "✅ 页面文件已更新: 初始 16GB, 最大 32GB" -ForegroundColor Green
    } else {
        Write-Host "创建新的页面文件配置..." -ForegroundColor Yellow
        $null = New-CimInstance -ClassName Win32_PageFileSetting -Property @{
            Name = "C:\\pagefile.sys"
            InitialSize = 16384
            MaximumSize = 32768
        }
        Write-Host "✅ 页面文件已创建: 初始 16GB, 最大 32GB" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "⚠️  请重启电脑使设置生效！" -ForegroundColor Yellow
    Write-Host "重启后运行: python train.py" -ForegroundColor Cyan

} catch {
    Write-Host "❌ 错误: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "请手动设置:" -ForegroundColor Yellow
    Write-Host "1. Win + R -> sysdm.clp" -ForegroundColor White
    Write-Host "2. 高级 -> 性能设置 -> 高级 -> 虚拟内存更改" -ForegroundColor White
    Write-Host "3. 自定义大小: 初始 16384 MB, 最大 32768 MB" -ForegroundColor White
}

pause
