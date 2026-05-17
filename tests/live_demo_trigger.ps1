# ==============================================================================
# SCRIPT DE DEMOSTRACIÓN AUTOMATIZADA - TFG EDGE SECURITY AGENT
# Compatible con Windows PowerShell 5.1 (Nativo)
# ==============================================================================

$TargetIP    = "192.168.1.141"
$TargetPort  = "8443"
$URL         = "https://$($TargetIP):$($TargetPort)/v1/global/health"
$ValidUser   = "admin"
$ValidPass   = "EdgeSec2026!"
$InvalidPass = "ClaveIncorrecta"
$MaxAttempts = 4

Clear-Host
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   Edge Security Agent — Iniciando Simulación de Ataque en Vivo       " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Objetivo: $URL" -ForegroundColor Yellow
Write-Host "Configuración: maxretry = 3 en la jaula 'nginx-http-auth'" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# PASO 1: Validar Acceso Legítimo
# ------------------------------------------------------------------------------
Write-Host "[*] Paso 1: Comprobando conexión legítima con credenciales válidas..." -ForegroundColor White

$ArgsValid = "-sk", "-u", "$($ValidUser):$($ValidPass)", $URL
$ResultValid = & curl.exe @ArgsValid

if ($ResultValid -like "*HEALTHY*") {
    Write-Host " -> [OK] Acceso legitimo concedido por Nginx (HTTP 200 / HEALTHY)" -ForegroundColor Green
} else {
    Write-Host " -> [ERROR] No se pudo validar el acceso legítimo inicial." -ForegroundColor Orange
    Write-Host " Detalles: $ResultValid"
    Exit
}

Write-Host "----------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# PASO 2: Simular Fuerza Bruta (Trigger de Fail2Ban)
# ------------------------------------------------------------------------------
Write-Host "[*] Paso 2: Iniciando bucle de $MaxAttempts intentos de ataque con claves incorrectas..." -ForegroundColor White

for ($i = 1; $i -le $MaxAttempts; $i++) {
    Write-Host " -> Lanzando intento de login fallido #$i..." -ForegroundColor Yellow
    
    $ArgsInvalid = "-sk", "-i", "-u", "$($ValidUser):$($InvalidPass)", $URL
    $Response = & curl.exe @ArgsInvalid 2>$null
    
    if ($Response -like "*401 Authorization Required*") {
        Write-Host "    [Respuesta] HTTP 401 Unauthorized (Nginx rechazo la clave)" -ForegroundColor Gray
    } 
    elseif ($Response -eq $null -or $Response.Count -eq 0 -or $error.Count -gt 0) {
        Write-Host "`n [BLOQUEADO] ¡El Firewall (iptables) ha cortado la conexion!" -ForegroundColor Red
        Write-Host " Fail2Ban ha detectado el patron y ha bloqueado tu IP local." -ForegroundColor Red
        break
    }
    
    Start-Sleep -Seconds 1
}

Write-Host "----------------------------------------------------------------------"
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   DEMOSTRACIÓN FINALIZADA — REVISA LA TERMINAL DE LA ORANGE PI       " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
