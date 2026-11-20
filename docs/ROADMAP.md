# Roadmap de Mejoras — Edge Security Agent

**Estado base:** v1.1.0 — 10/10 lotes cerrados, purga histórica completa, CI verde (x86_64 + ARM64).
Las tareas son opcionales; las que implican reescritura de historia o cambios de firewall requieren **aprobación explícita del owner**.

Prioridades: 🔴 Alta · 🟡 Media · 🟢 Baja

## 1. Higiene del repositorio
| # | Tarea | Prioridad | Notas |
|---|---|---|---|
| P1.1 | Purga de bloat: `picoclaw_aarch64.deb` (~20 MB) del histórico | 🟢 | No es secreto; reduciría `.git` de 21M a ~2M. Requiere `filter-repo` + `--force`. |
| P1.2 | Limpiar "runs fantasma" de Actions (SHA pre-purga) | 🟢 | Solo estético; se autopurgan con el tiempo o vía API/soporte. |
| P1.3 | `pre-commit` con ruff/mypy + detección de secretos (gitleaks) | 🟡 | Evita reintroducir literales (lección aprendida). |

## 2. Seguridad
| # | Tarea | Prioridad | Notas |
|---|---|---|---|
| P2.1 | Rotar `SECRET_KEY` (placeholder en `secrets.env`) | 🟡 | No usado hoy para sesiones; dejado consistente. |
| P2.2 | Alertas proactivas (Telegram) ante umbrales (temp, RAM, score) | 🟡 | Cadena `mcp_tools → legacy/scripts/telegram-notify.sh`. |
| P2.3 | Verificación de integridad periódica de `history.db` | 🟢 | `backup.timer` ya verifica al respaldar. |
| P2.4 | Firma/verificación de artefactos de release (SBOM) | 🟢 | Supply chain. |

## 3. Calidad y pruebas
| # | Tarea | Prioridad | Notas |
|---|---|---|---|
| P3.1 | Subir coverage (>55%) | 🟡 | Foco en `src/agent.py` y rutas no cubiertas de `sec_web.py` (70%). |
| P3.2 | Ampliar tests de integración en CI | 🟡 | Hoy solo `test_chat_integration_runs_real_agent`. |
| P3.3 | Test de contrato contra `docs/api_spec.yaml` | 🟢 | Validar que los endpoints cumplen el esquema. |
| P3.4 | Rehabilitar/limpiar herramientas de `legacy/` o eliminarlas | 🟢 | Decidir soporte o retirada definitiva. |

## 4. Operación y observabilidad
| # | Tarea | Prioridad | Notas |
|---|---|---|---|
| P4.1 | Dashboards/alertas Prometheus (Grafana en nodo auxiliar) | 🟡 | `/metrics` ya expone score, temp, RAM, ssh_failures. |
| P4.2 | `update.timer` opt-in: validar flujo de rollback en staging | 🟢 | Ejercitar `update_safe.sh` end-to-end. |
| P4.3 | Notas de capacidad (RAM/térmico) para cargas LLM mayores | 🟢 | tinyllama:1.1b actual. |

## 5. Plataforma (largo plazo)
| # | Tarea | Prioridad | Notas |
|---|---|---|---|
| P5.1 | HA multi-nodo (agregación de métricas) | 🟢 | Fuera del alcance mono-nodo actual. |
| P5.2 | Análisis/anomalías con modelo local propio | 🟢 | Depende de capacidad del hardware. |
| P5.3 | Endurecimiento adicional: SELinux/AppArmor perfil dedicado | 🟢 | systemd ya aplica `ProtectSystem=strict`. |

## Criterio de aceptación por tarea
- Cambios de código: `pytest`, `ruff`, `mypy`, `compileall`, `bash -n` en verde.
- Cambios de CI/infra: workflow verde en **ambas** arquitecturas.
- Reescrituras de historia / firewall / systemd: backup previo en `/var/backups/edge-sec-agent/` + aprobación del owner.
