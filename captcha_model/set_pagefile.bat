@echo off
echo Setting virtual memory (page file)...
echo.

powershell -Command ^
  "$pageFile = Get-WmiObject Win32_PageFileSetting;" ^
  "if ($pageFile) { $pageFile.InitialSize = 16384; $pageFile.MaximumSize = 32768; $pageFile.Put() | Out-Null; Write-Host 'Success: Page file updated to 16GB-32GB' -ForegroundColor Green }" ^
  "else { Write-Host 'Creating new page file...' -ForegroundColor Yellow; Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{Name='C:\\pagefile.sys'; InitialSize=16384; MaximumSize=32768} | Out-Null; Write-Host 'Success: Page file created (16GB-32GB)' -ForegroundColor Green }"

echo.
echo ========================================
echo Please RESTART your computer to apply changes!
echo ========================================
echo.
echo After restart, run: python train.py
echo.
pause
