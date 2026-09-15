# NEXUS Market Agent V0.16.1.1 — ONLINE + LIVE PAPER + SHADOW LEARNING

V0.16 mantiene el agente autónomo PAPER de V0.15 y agrega aprendizaje controlado de resultados.

## Nuevo en V0.16

- Aprendizaje PAPER en sombra: guarda decisiones e indicadores existentes en el momento de cada muestra.
- Evalúa qué ocurrió después a 1 hora, 1 día y 5 días.
- Resume hit rate de decisión y retorno posterior por tipo de acción.
- Ajuste interno opcional y acotado del `ai_strength_score`: máximo ±3 puntos y solo tras muestra suficiente.
- **No cambia automáticamente estrategias validadas, stop, target ni reglas de broker.**
- Acciones fraccionarias PAPER para emisoras de EE.UU. con capital pequeño.
- Trading real sigue deshabilitado y requiere intermediario autorizado + confirmación manual.

## Filosofía de seguridad

El aprendizaje no convierte los scores en probabilidades de ganar. Es una capa experimental que mide desempeño posterior y busca detectar si las decisiones PAPER están aportando señal fuera de muestra. Resultados pasados no garantizan resultados futuros.

## Render

Build: `pip install -r requirements.txt`

Start: `gunicorn app:app --workers 1 --threads 4 --timeout 240`
