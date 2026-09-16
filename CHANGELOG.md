# V0.16.3 FIX — Yahoo/Render

- Corrige `Invalid Crumb` / HTTP 401 de yfinance en Render usando Yahoo chart API como ruta primaria.
- yfinance queda como respaldo.
- Circuit breaker de 15 min tras fallos para evitar tormentas de solicitudes.
- Cache LIVE de 2 min y fallback stale controlado.
- Restaura `get_live_price` como método de `YFinanceProvider`.
- No cambia Shadow Learning, contrafactual, calibración ni reglas PAPER.
- Trading real continúa deshabilitado.

## V0.16.2
- Motor contrafactual PAPER a 1 día.
- Detecta oportunidades perdidas, entradas evitadas y compras favorables/desfavorables.
- Anti-duplicación: una decisión idéntica en el mismo régimen no vuelve a contar durante 4 horas.
- Auditoría contextual empresa + régimen + sector + acción.
- Confianza por tamaño de muestra.
- Nuevo panel Errores y oportunidades y endpoint /api/learning/counterfactual.
- Trading real continúa bloqueado.

## V0.16.1 FIX
- Sincroniza etiquetas visibles, título y cache-busting del frontend con V0.16.1.
- Corrige texto de alerta de prueba Telegram.
- No cambia la lógica PAPER, aprendizaje ni trading real (sigue deshabilitado).

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


## V0.16.3
- Calibración multi-horizonte 1h/1d/5d.
- Nivel de evidencia por tamaño de muestra.
- Retorno neto estimado después de fricción PAPER.
- Endpoint `/api/learning/calibration`.
- Panel Calibración y evidencia.
- Sin trading real ni cambios automáticos de estrategias.
