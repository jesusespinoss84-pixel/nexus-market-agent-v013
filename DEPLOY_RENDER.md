# Publicar NEXUS V0.13 en Internet

La aplicación ya está preparada para GitHub + Render.

## Opción recomendada
1. Subir el contenido de esta carpeta a un repositorio privado de GitHub.
2. En Render crear un Blueprint/Web Service desde el repositorio.
3. Usar `render-persistente.yaml` si la cuenta/plan permite disco persistente.
4. Si no se usa disco, `render.yaml` funciona, pero PAPER Portfolio y caches podrían reiniciarse cuando el servidor se reconstruya.
5. Al terminar el despliegue, Render entrega una URL HTTPS pública.

El servicio debe usar UN solo worker. V0.13 incluye un scheduler interno y múltiples workers provocarían escaneos duplicados.

Variables admitidas:
- `PORT` — la establece normalmente el hosting.
- `NEXUS_DATA_DIR` — directorio de datos persistentes.
- `NEXUS_SCAN_MINUTES` — intervalo del escáner.
- `NEXUS_LIVE_MINUTES` — intervalo de actualización de posiciones PAPER.

El endpoint `/healthz` permite al hosting verificar que la aplicación está viva.
