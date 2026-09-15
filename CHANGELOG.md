## V0.16.1
- Memoria y auditoría PAPER por empresa, régimen y sector.
- Regímenes: ALCISTA, BAJISTA, LATERAL, ALTA_VOLATILIDAD, RISK_OFF.
- Promoción: EXPERIMENTAL, PAPER, CANDIDATA A REVISIÓN REAL.
- Guardrails: no modifica pesos automáticamente y trading real permanece bloqueado.

# CHANGELOG

## V0.16.1.1
- Shadow learning PAPER con horizontes 1h/1d/5d.
- Registro de features de cada decisión.
- Estadísticas de hit rate y retorno posterior.
- Ajuste IA acotado ±3 puntos tras muestra mínima; no cambia estrategias automáticamente.
- Soporte de acciones fraccionarias PAPER para EE.UU.
- Nuevo panel y APIs `/api/learning/status` y `/api/learning/samples`.
- Trading real permanece bloqueado.
