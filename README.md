# NEXUS Market Agent V0.16.3 — CALIBRACIÓN + EVIDENCIA + FRICCIÓN PAPER

V0.16.3 conserva V0.16.2 y agrega una capa de calibración auditable.

- Compara resultados maduros a 1 hora, 1 día y 5 días.
- Clasifica evidencia como INSUFICIENTE, INICIAL, MODERADA o SÓLIDA según muestra independiente.
- Reporta retorno bruto y retorno PAPER estimado después de slippage, comisión y buffer USD/MXN.
- Mantiene contrafactual, anti-duplicación, auditor por contexto y acciones fraccionarias PAPER.
- No cambia automáticamente pesos de estrategias validadas.
- Trading real continúa deshabilitado.
- Los scores y niveles de evidencia son métricas internas de investigación, no probabilidades de ganar.

## Render
Build: `pip install -r requirements.txt`

Start: `gunicorn app:app --workers 1 --threads 4 --timeout 240`
