# Instalación doméstica en Windows

El host debe ser Windows 10/11 x64 con PowerShell 5.1 o superior, `uv`
instalado y una IPv4 privada fija o reservada por DHCP. La aplicación quedará
disponible únicamente en `http://<IP-privada>:8080` para equipos de la misma
red. Este transporte no cifra credenciales ni datos: no abras el puerto en el
router ni uses esta instalación en una red pública o no confiable.

## Preparación

1. Reserva en el router la IPv4 privada del servidor y confirma que el perfil
   de la conexión de Windows es **Privado**.
2. En el repositorio ejecuta `pwsh scripts/build.ps1`. El wheel queda en
   `backend/dist/` e incluye la SPA construida.
3. Abre Windows PowerShell como Administrador. No copies contraseñas, IP,
   rutas domésticas ni contenido financiero a incidencias o al repositorio.

## Instalación

Ejecuta desde la raíz del repositorio y sustituye solo los valores locales:

```powershell
.\deploy\windows\Install-PersonalFinance.ps1 `
  -WheelPath .\backend\dist\personal_finance-0.1.0-py3-none-any.whl `
  -ServerIp <IP-privada> `
  -StablePrivateIPv4Confirmed `
  -BootstrapUsername <usuario> `
  -SpaceName <hogar>
```

La contraseña inicial se solicita de forma interactiva por el CLI; nunca se
acepta como argumento. El instalador:

- crea un Python 3.13 administrado por `uv` en
  `%ProgramFiles%\PersonalFinance`;
- conserva configuración, SQLite, logs y copias en
  `%ProgramData%\PersonalFinance`;
- genera `PF_SECRET_KEY` y un JSON protegido por ACL para Administradores,
  SYSTEM y `LOCAL SERVICE`;
- registra `PersonalFinance-App` al arrancar el sistema y
  `PersonalFinance-Backup` a diario, ambas bajo `LOCAL SERVICE` y con
  recuperación de ejecuciones perdidas;
- crea una regla entrante TCP 8080 limitada a perfil Privado y
  `LocalSubnet`.

`PF_TRANSPORT_MODE=http_lan` y
`PF_ALLOWED_ORIGIN=http://<IP-privada>:8080` se fijan expresamente. Los scripts
leen el JSON y cargan cada valor en el entorno del proceso; no pasan secretos
por la línea de comandos.

## Comprobación inicial

```powershell
.\deploy\windows\Test-PersonalFinance.ps1 -ServerIp <IP-privada>
```

Después abre `http://<IP-privada>:8080` desde otro ordenador Windows de la LAN.
El acceso desde Internet y desde perfiles Público o Dominio queda fuera de
alcance y debe seguir bloqueado.
