# Execucao diaria local do video-diario-ia (chamada pelo Agendador de Tarefas do Windows).
# - Roda no maximo 1 vez por dia (marca em saida\_agendado_ultimo.txt).
# - Espera ate 60 min pela internet antes de comecar.
# - Atualiza o codigo (git pull) e dispara a rotina no GitHub (o video e feito e publicado la).
# Agendar/desagendar: agendar_local.ps1 (ou: agendar_local.ps1 -Remover)
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
$saida = Join-Path $raiz "saida"
New-Item -ItemType Directory -Force $saida | Out-Null
$log = Join-Path $saida "_agendado.log"
$marca = Join-Path $saida "_agendado_ultimo.txt"
$hoje = (Get-Date).ToString("yyyy-MM-dd")
function Log($m) { "[{0}] {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $m | Out-File -Append -Encoding utf8 $log }

if ((Test-Path $marca) -and ((Get-Content $marca -Raw).Trim() -eq $hoje)) { exit 0 }

# trava contra duas execucoes ao mesmo tempo (ex.: horario + logon)
$trava = Join-Path $saida "_agendado.lock"
if (Test-Path $trava) {
    if (((Get-Date) - (Get-Item $trava).LastWriteTime).TotalHours -lt 5) { exit 0 }
}
Set-Content $trava $PID

try {
    $online = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 15 -Uri "https://api.github.com" | Out-Null
            $online = $true; break
        } catch { Start-Sleep -Seconds 60 }
    }
    if (-not $online) { Log "sem internet por 60 min; tento de novo no proximo gatilho"; exit 1 }

    Log "inicio"
    $git = & git pull --ff-only 2>&1 | Out-String
    Log ("git pull: " + $git.Trim())

    # o agendamento do GitHub atrasa horas: o PC dispara a rotina de la na hora certa,
    # se ainda nao houve video do dia (concluido com sucesso ou em andamento) no GitHub
    # O video e feito no GitHub (onde ele e publicado). O PC nao gera um segundo video (gastava cota e CPU
    # e nao ia para lugar nenhum): so dispara a rotina de la na hora certa, se ainda nao houve video do dia.
    try {
        $runs = & gh run list --workflow video-diario.yml --limit 40 --json displayTitle,createdAt,status,conclusion | ConvertFrom-Json
        $feitos = @($runs | Where-Object {
            -not $_.displayTitle.StartsWith("Refazer") -and
            ([DateTime]$_.createdAt).ToLocalTime().ToString("yyyy-MM-dd") -eq $hoje -and
            ($_.status -ne "completed" -or $_.conclusion -eq "success") })
        if ($feitos.Count -eq 0) {
            & gh workflow run video-diario.yml --ref main 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "gh workflow run falhou (codigo $LASTEXITCODE)" }
            Log "GitHub: rotina disparada"
        } else {
            Log "GitHub: ja ha video do dia ($($feitos.Count)); nao disparei"
        }
        Set-Content $marca $hoje
        Log "ok"
    } catch { Log "GitHub: nao consegui disparar ($($_.Exception.Message)); tento de novo no proximo gatilho" }
} finally {
    Remove-Item $trava -ErrorAction SilentlyContinue
}
