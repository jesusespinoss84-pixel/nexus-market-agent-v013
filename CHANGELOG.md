
## V0.26.5
- Corrige versionado visible de toda la interfaz a V0.26.5.
- Corrige `config/settings.yaml` a `version: 0.26.5`.
- Incrementa cache-busting de CSS/JS a `v=0263`.
- Mantiene Bridge V4.3 con fallback manual TWS auditado como `MANUAL_TWS_PRICE`.
- Mantiene PAPER-only, rechazo de cuentas LIVE, guarda de precio 2.5%, máximo 1 acción/USD 500/LMT DAY y precauciones TWS.

# V0.16.5

- Corrige etiqueta interna a SHADOW_LEARNING_0165.
- Nuevo panel Madurez del aprendizaje: 1 h, 1 día y 5 días.
- Muestra maduras, pendientes y cobertura por horizonte.
- El ajuste IA permanece bloqueado hasta reunir muestra PAPER BUY suficiente a 1 día.
- Ajuste interno más conservador: compara consistencia 1 h vs 1 día y atenúa señales contradictorias.
- Mantiene límite global de ajuste, no cambia pesos de estrategia.
- Risk Governor y stress tests V0.16.4 se conservan.
- Trading real continúa deshabilitado; PAPER únicamente.

## V0.17
- Broker Gateway para Interactive Brokers (IBKR), desacoplado del motor PAPER.
- Estado de sesión/autenticación IBKR.
- Consulta de cuentas preparada.
- What-If/preview de orden para comisión, coste e impacto cuando IBKR Gateway está disponible.
- Borrador auditable de orden.
- Endpoint de envío real explícitamente bloqueado (HTTP 403).
- PAPER, aprendizaje, validación, Risk Governor y stress tests permanecen intactos.

## V0.25.0
- Ciclo de operación PAPER ampliado.
- Validación automática acelerada a 6 candidatas por scan.
- Monitor de posiciones con distancias a stop/objetivo y tiempo abierto.
- Endpoint de borrador de orden PAPER sin transmisión al broker.
