# RECUPERACIÓN DE SESIÓN INTERRUMPIDA

La ejecución anterior fue interrumpida.

No supongas que ninguna tarea terminó correctamente.

Primero:

```bash
git status --short
git branch --show-current
git log -3 --oneline
```

Después lee:

- `AGENTS.md`;
- `OPENCODE_EDGE_SEC_AGENT_MASTER_PROMPT.md`;
- los archivos modificados;
- los últimos logs disponibles;
- el estado actual de la Orange Pi.

Determina:

1. Qué fase estaba en curso.
2. Qué comandos sí se ejecutaron.
3. Qué cambios sí están aplicados.
4. Qué backups existen.
5. Qué servicios están activos.
6. Qué pruebas faltan.
7. Si existe riesgo de repetir una operación.

No repitas una instalación ni un cambio crítico sin comprobar primero su estado actual.

Reanuda desde el último punto confirmado en `AGENTS.md`.

Si el estado no puede determinarse con evidencia, marca esa parte como `NO VERIFICADO` y realiza una auditoría antes de continuar.
