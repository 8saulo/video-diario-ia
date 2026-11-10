# Agenda a execucao diaria local: todo dia as 05:00 UTC (02:00 de Brasilia) e ao entrar no Windows.
# Se o PC estiver desligado no horario, roda assim que ligar (com internet). No maximo 1 video por dia.
# Uso:  powershell -ExecutionPolicy Bypass -File agendar_local.ps1          (agenda)
#       powershell -ExecutionPolicy Bypass -File agendar_local.ps1 -Remover (remove)
param([switch]$Remover)
$nome = "video-diario-ia"
if ($Remover) { Unregister-ScheduledTask -TaskName $nome -Confirm:$false; "removida"; exit }

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $raiz "rodar_diario.ps1"
$hora = [DateTime]::SpecifyKind((Get-Date).Date.AddHours(5), [DateTimeKind]::Utc).ToLocalTime()

$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" -WorkingDirectory $raiz
$gatilhos = @(
    (New-ScheduledTaskTrigger -Daily -At $hora),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 5) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilhos -Settings $ajustes `
    -Description "Gera o video diario (05:00 UTC ou ao entrar no Windows, 1 vez por dia)" -Force | Out-Null
"agendada: todo dia as {0:HH:mm} (horario local) e ao entrar no Windows" -f $hora
