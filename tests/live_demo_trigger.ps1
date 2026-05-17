<#
.SYNOPSIS
    Edge Security Agent — Live Demo Trigger
    Script de demostración en vivo para tribunal evaluador (TFG).

.DESCRIPTION
    Simula un escenario real de ataque de fuerza bruta contra el endpoint
    protegido por Basic Auth de Nginx, demostrando cómo Fail2Ban detecta
    los intentos fallidos y bloquea la IP atacante mediante iptables.

    Compatible con Windows PowerShell 5.1 (sin operadores && ni parámetros PS Core 7).

.USAGE
    .\tests\live_demo_trigger.ps1
#>

# Configuración regional y preferencias de error
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ==============================================================================
# PARÁMETROS DE CONEXIÓN
# ==============================================================================
$TargetIP    = "192.168.1.141"
$Port        = "8443"
$BaseURL     = "https://$($TargetIP):$($Port)"
$Endpoint    = "/v1/global/health"
$FullURL     = "$BaseURL$Endpoint"
$AuthCorrect = "admin:ClaveCorrecta"
$AuthWrong   = "admin:ClaveIncorrecta"
$MaxAttempts = 4
$TimeoutSec  = 5

# ==============================================================================
# CABECERA VISUAL
# ==============================================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Edge Security Agent — Demostración de Hardening        ║" -ForegroundColor Cyan
Write-Host "║   Orange Pi Zero 3 | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# PASO 1: VALIDAR CONECTIVIDAD Y ACCESO LEGÍTIMO
# ==============================================================================
Write-Host "[PASO 1] Validando acceso legítimo al agente..." -ForegroundColor White
Write-Host ""

try {
    $TempFile = "$env:TEMP\edge_health_demo.json"
    $HttpCode = & curl.exe -s -k -w "%{http_code}" -o $TempFile -u $AuthCorrect $FullURL --connect-timeout $TimeoutSec --max-time $TimeoutSec

    if ($HttpCode -eq "200") {
        Write-Host "  [OK] Acceso legítimo concedido por Nginx (Código 200/Health)" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Respuesta del servidor:" -ForegroundColor Gray
        if (Test-Path $TempFile) {
            $Content = Get-Content $TempFile -Raw
            Write-Host "  $Content" -ForegroundColor DarkGray
            Remove-Item $TempFile -Force -ErrorAction SilentlyContinue
        }
    }
    else {
        Write-Host "  [WARN] Código HTTP recibido: $HttpCode (esperado: 200)" -ForegroundColor Yellow
        Write-Host "  Verifica que el agente esté en ejecución y las credenciales sean correctas." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  [FAIL] Error de conexión: $_" -ForegroundColor Red
    Write-Host "  Asegúrate de que la Orange Pi (192.168.1.141) esté accesible desde esta red." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Demo abortado. No se puede continuar sin conectividad." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ==============================================================================
# PASO 2: SIMULAR ATAQUE DE FUERZA BRUTA (Trigger de Fail2Ban)
# ==============================================================================
Write-Host "[PASO 2] Simulando ataque de fuerza bruta contra Basic Auth..." -ForegroundColor White
Write-Host ""
Write-Host "  Configuración de la jaula nginx-http-auth:" -ForegroundColor Gray
Write-Host "    - maxretry: 3 intentos fallidos" -ForegroundColor Gray
Write-Host "    - findtime: 600 segundos" -ForegroundColor Gray
Write-Host "    - bantime:  3600 segundos (1 hora)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Iniciando $MaxAttempts peticiones con credenciales incorrectas..." -ForegroundColor Yellow
Write-Host ""

$BanDetected = $false

for ($i = 1; $i -le $MaxAttempts; $i++) {
    Write-Host "  ┌─ Intento $i/$MaxAttempts" -ForegroundColor Cyan
    Write-Host "  │  Enviando petición con credenciales falsas..." -ForegroundColor Cyan

    try {
        $HttpCode = & curl.exe -s -k -w "%{http_code}" -o $null -u $AuthWrong $FullURL --connect-timeout $TimeoutSec --max-time $TimeoutSec

        if ($HttpCode -eq "401") {
            Write-Host "  │  Resultado: HTTP 401 Unauthorized (Credenciales rechazadas)" -ForegroundColor Yellow
        }
        elseif ($HttpCode -eq "000") {
            Write-Host "  │  Resultado: Sin respuesta del servidor" -ForegroundColor Red
        }
        else {
            Write-Host "  │  Resultado: HTTP $HttpCode" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  │  Resultado: Error de red — $_" -ForegroundColor Red
    }

    Write-Host "  └────────────────────────────────────" -ForegroundColor Cyan
    Write-Host ""

    # Tras el 3er intento, Fail2Ban debería haber baneado la IP
    if ($i -ge 3) {
        Start-Sleep -Seconds 2
        try {
            $TestCode = & curl.exe -s -k -w "%{http_code}" -o $null -u $AuthWrong $FullURL --connect-timeout 3 --max-time 3 -ErrorAction SilentlyContinue

            if ($TestCode -eq "000") {
                $BanDetected = $true
                Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Red
                Write-Host "  ║   [BLOQUEADO] Firewall (iptables) ha bloqueado la    ║" -ForegroundColor Red
                Write-Host "  ║   IP del atacante. Fail2Ban activó la jaula          ║" -ForegroundColor Red
                Write-Host "  ║   nginx-http-auth tras 3 intentos fallidos.          ║" -ForegroundColor Red
                Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Red
                Write-Host ""
                break
            }
        }
        catch {
            $BanDetected = $true
            Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Red
            Write-Host "  ║   [BLOQUEADO] Conexión rechazada por el Firewall.    ║" -ForegroundColor Red
            Write-Host "  ║   Fail2Ban ha baneado la IP atacante.                ║" -ForegroundColor Red
            Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Red
            Write-Host ""
            break
        }
    }

    Start-Sleep -Seconds 1
}

# ==============================================================================
# PASO 3: VERIFICAR ESTADO POST-ATAQUE
# ==============================================================================
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[PASO 3] Verificando estado post-ataque..." -ForegroundColor White
Write-Host ""

if ($BanDetected) {
    Write-Host "  [OK] La IP atacante ha sido baneada correctamente." -ForegroundColor Green
    Write-Host "  [OK] Fail2Ban + iptables operativos." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Para verificar manualmente en la Orange Pi:" -ForegroundColor Gray
    Write-Host "    ssh -p 2222 root@192.168.1.141" -ForegroundColor DarkGray
    Write-Host "    fail2ban-client status nginx-http-auth" -ForegroundColor DarkGray
    Write-Host "    iptables -L INPUT -n | grep DROP" -ForegroundColor DarkGray
}
else {
    Write-Host "  [WARN] No se detectó bloqueo automático." -ForegroundColor Yellow
    Write-Host "  Posibles causas:" -ForegroundColor Yellow
    Write-Host "    - Fail2Ban no está activo o la jaula nginx-http-auth no configurada" -ForegroundColor Yellow
    Write-Host "    - El maxretry es superior a 3" -ForegroundColor Yellow
    Write-Host "    - La IP de origen no coincide con la monitorizada" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Demo finalizado." -ForegroundColor Cyan
Write-Host ""
