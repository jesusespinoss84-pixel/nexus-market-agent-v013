# NEXUS Market Agent V0.14.0 — ONLINE + LIVE PAPER

Corrección del conflicto de puerto local de V0.13.

## Puerto automático
NEXUS intenta usar 5130. Si ya está ocupado, busca automáticamente un puerto libre entre 5131 y 5199.

La consola muestra el puerto elegido y el navegador se abre solo en la dirección correcta.

No necesitas cerrar otro proyecto, matar procesos, desactivar firewall ni cambiar permisos.

Ejemplo:
- 5130 ocupado
- NEXUS detecta 5131 libre
- abre `http://127.0.0.1:5131`

En Internet, si el hosting define la variable `PORT`, NEXUS respeta exactamente ese puerto.

## Uso local
1. `INSTALAR_V013_1.bat`
2. `EJECUTAR_WEB_V013_1.bat`
3. El navegador se abrirá automáticamente.

Mantiene ONLINE READY + LIVE PAPER de V0.13.


## V0.14
- Centro de operación PAPER manual con monto, stop y objetivo.
- Panel de NEXUS AI con acción asistida (PAPER BUY / ESPERAR / ESTUDIAR / PAUSAR).
- Centro de alertas del navegador y soporte opcional de Telegram mediante variables de entorno.
- Accesos directos a planes, facturación y servicio de Render.
- Centro legal CNBV y estado de trading real.
- Trading real deshabilitado por defecto y limitado a futura confirmación manual mediante broker compatible.
