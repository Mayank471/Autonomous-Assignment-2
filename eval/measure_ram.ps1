# Samples memory every 2 s while a command runs and prints the peaks.
#   powershell -File eval\measure_ram.ps1 -Command "python eval\smoke_test.py"
# Columns: system RAM in use (total - available), working set of the Ollama server and its llama-server model runners (
# the chat and embedding models), working set of python processes (agent, ChromaDB, BM25).
param([Parameter(Mandatory = $true)][string]$Command, [string]$Out = "eval\results\ram_samples.csv")

$total = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $Command" -PassThru -NoNewWindow
$rows = @()
$t0 = Get-Date
while (-not $proc.HasExited) {
    $os = Get-CimInstance Win32_OperatingSystem
    $used = $total - ($os.FreePhysicalMemory / 1MB)
    $ollama = (Get-Process -Name "ollama*","llama-server*" -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1GB
    $py = (Get-Process -Name "python*" -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1GB
    $rows += [pscustomobject]@{ t_s = [int]((Get-Date) - $t0).TotalSeconds; system_used_gb = [math]::Round($used, 2);
                                ollama_gb = [math]::Round($ollama, 2); python_gb = [math]::Round($py, 2) }
    Start-Sleep -Seconds 2
}
$rows | Export-Csv -NoTypeInformation -Path $Out
"Total RAM: {0:N1} GB; samples: {1}; duration: {2} s" -f $total, $rows.Count, [int]((Get-Date) - $t0).TotalSeconds
"Peak system RAM in use: {0} GB" -f ($rows | Measure-Object system_used_gb -Maximum).Maximum
"Peak Ollama working set: {0} GB" -f ($rows | Measure-Object ollama_gb -Maximum).Maximum
"Peak python working set: {0} GB" -f ($rows | Measure-Object python_gb -Maximum).Maximum
"Exit code of command: $($proc.ExitCode)"
