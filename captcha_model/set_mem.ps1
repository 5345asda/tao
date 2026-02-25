Write-Host "Setting page file to 16GB-32GB..." -ForegroundColor Cyan

try {
    $pfs = Get-WmiObject Win32_PageFileSetting
    foreach ($pf in $pfs) {
        $pf.InitialSize = 16384
        $pf.MaximumSize = 32768
        $pf.Put() | Out-Null
    }
    Write-Host "SUCCESS! Page file updated." -ForegroundColor Green
    Write-Host "Please restart your computer." -ForegroundColor Yellow
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}
