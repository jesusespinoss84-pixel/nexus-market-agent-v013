# NEXUS Market Agent V0.16.5 — MADUREZ + CONSISTENCIA DE APRENDIZAJE PAPER

Control superior de riesgo PAPER con estados NORMAL / PRECAUCIÓN / DEFENSIVO / PAUSA, límites de exposición y pruebas de estrés. Trading real permanece deshabilitado.

## V0.17 — Broker Gateway IBKR
Esta versión añade una capa de integración con Interactive Brokers sin habilitar ejecución automática ni transmisión de órdenes reales. El gateway soporta estado, lectura de cuentas, What-If y borradores auditables. `/api/broker/submit` está bloqueado deliberadamente.

Para cliente retail, el Client Portal Gateway de IBKR normalmente se ejecuta localmente. Variables opcionales: `NEXUS_IBKR_BASE_URL` y `NEXUS_IBKR_ACCOUNT_ID`. En Render, `localhost` corresponde al servidor de Render, no a tu PC; por ello se requiere una arquitectura segura adicional antes de enlazar un gateway local.
