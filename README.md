
## Descripción

Pipeline CI/CD de extremo a extremo. Una aplicación Flask que monitorea el
estado de varias APIs públicas se despliega automáticamente en un servidor
cada vez que se hace `git push` a la rama `main`. GitHub Actions ejecuta las
pruebas, se conecta al servidor por SSH sin contraseña, actualiza el código y
reinicia el servicio.

Flujo completo:

```
git push  →  GitHub Actions corre pruebas  →  SSH al servidor
          →  git pull en el servidor  →  reinicia el servicio  →  dashboard actualizado
```

## Arquitectura

| Componente | Función |
|---|---|
| Flask + gunicorn | Sirve el dashboard y el endpoint `/api/estado` en el puerto 5000 |
| systemd | Mantiene la app corriendo y la reinicia si falla (`dashboard.service`) |
| nginx | Proxy inverso: recibe en el puerto 80 y reenvía al 5000 |
| GitHub Actions | Ejecuta pruebas y dispara el deploy por SSH |
| Oracle Cloud (VPS) | Servidor Ubuntu 22.04 con IP pública donde vive la app |

El servidor es una instancia Always Free de Oracle Cloud (shape
VM.Standard.E2.1.Micro), con swap de 2 GB añadido por la limitación de 1 GB
de RAM.

## Servicios monitoreados

La app consulta periódicamente estos endpoints y clasifica cada uno como
activo (HTTP < 400) o caído:

- GitHub API
- JSONPlaceholder
- HTTPBin
- ReqRes
- Una API local (puerto 5001) que se marca como caída si no está levantada

El dashboard se refresca automáticamente cada 30 segundos.

## Requisitos

```
pip install -r requirements.txt
```

Contenido de `requirements.txt`: flask, requests, gunicorn.

## Estructura del proyecto

```
dashboard-estatus/
├── .github/workflows/
│   └── deploy.yml        CI/CD: pruebas + deploy por SSH
├── templates/
│   └── index.html        Dashboard web (auto-refresca cada 30s)
├── app.py                Flask: /api/estado + / (dashboard)
├── test_app.py           Pruebas unitarias con mocks
├── requirements.txt      flask, requests, gunicorn
├── dashboard.service     Unit file de systemd
├── .gitignore
└── README.md
```

## Puesta en marcha del servidor (una sola vez)

1. Instalar dependencias:
   ```
   sudo apt update && sudo apt install -y python3 python3-venv git nginx
   ```
2. Crear usuario dedicado `deploy` y la carpeta `/opt/dashboard`.
3. Otorgar a `deploy` permiso sudo acotado para reiniciar solo el servicio:
   ```
   deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart dashboard
   ```
4. Clonar el repositorio en `/opt/dashboard`, crear el venv e instalar
   dependencias.
5. Registrar el servicio systemd y arrancarlo:
   ```
   sudo systemctl enable --now dashboard
   ```
6. Configurar nginx como proxy inverso hacia el puerto 5000.

## Configuración del CI/CD

Se genera un par de llaves SSH exclusivo para el pipeline. La llave pública se
instala en `~/.ssh/authorized_keys` del usuario `deploy`; la llave privada se
guarda cifrada en los Secrets del repositorio.

Secrets configurados en GitHub (Settings → Secrets and variables → Actions):

| Secret | Contenido |
|---|---|
| `SSH_PRIVATE_KEY` | Llave privada de deploy |
| `SERVER_HOST` | IP pública del servidor |
| `SERVER_USER` | `deploy` |

## Respuestas del checklist

### ¿Por qué el job `deploy` usa `needs: test`?

`needs: test` crea una dependencia: el deploy no arranca hasta que las pruebas
terminen con éxito. Sin esa línea, GitHub Actions correría ambos jobs en
paralelo y se podría desplegar código roto a producción aunque las pruebas
hubieran fallado. Es la puerta de calidad que da sentido a la integración
continua.

### ¿Qué hace `ssh-keyscan` y por qué es necesario en CI?

`ssh-keyscan` consulta la clave pública del host y la agrega a `known_hosts`.
En una sesión interactiva, SSH pregunta si se confía en el fingerprint la
primera vez; un runner de CI es efímero y no hay nadie que responda, así que la
conexión se colgaría. Pre-cargar el host key evita esa pregunta.

En esta práctica se optó por un enfoque equivalente y más robusto en CI:
omitir la verificación con las opciones `-o StrictHostKeyChecking=no` y
`-o UserKnownHostsFile=/dev/null` directamente en el comando ssh, ya que
`ssh-keyscan` resultó frágil dentro del runner.

### ¿Por qué `set -e` al inicio del script SSH?

`set -e` hace que el shell aborte al primer comando que devuelva un código
distinto de cero. Sin él, si `git pull` fallara por un conflicto, el script
seguiría de largo y ejecutaría `systemctl restart` de todos modos, reiniciando
el servicio con código a medias y reportando éxito. Con `set -e`, cualquier
fallo detiene el deploy y marca el pipeline en rojo.

### Romper una prueba a propósito

Al modificar una aserción de `test_app.py` para que falle y hacer push, el job
`test` termina en rojo y el job `deploy` queda como *skipped* (no se ejecuta),
gracias a `needs: test`. El servidor conserva la versión anterior intacta. Al
revertir el cambio y volver a hacer push, ambos jobs vuelven a verde y el
deploy se completa. Esto demuestra que el pipeline protege producción de código
defectuoso.

## Hallazgos durante la implementación

Estos problemas surgieron en la práctica real y su resolución forma parte del
aprendizaje:

- **Regla REJECT de iptables en Oracle.** La imagen de Ubuntu de Oracle Cloud
  trae iptables con una regla `REJECT all` preinstalada. Abrir el puerto 80 en
  la Security List de la consola web no basta: hay que agregar la regla ACCEPT
  en iptables, y además insertarla ANTES del REJECT. Al colocarla después, el
  tráfico se rechazaba antes de llegar a nginx (síntoma: timeout). La solución
  robusta fue usar `iptables -I INPUT 1` para forzar la primera posición.

- **Dos capas de firewall.** Oracle exige abrir el puerto en dos lugares
  independientes: la Security List de la VCN (consola) y iptables (dentro de la
  VM). Omitir cualquiera de las dos produce un timeout idéntico.

- **Rama `master` vs `main`.** Al reinicializar el repositorio en el servidor
  con `git init`, la rama local quedó como `master`, mientras que GitHub usa
  `main`. Esto rompía el `git pull origin main` del pipeline. Se corrigió
  reclonando el repositorio para alinear ambas ramas.

- **Formato de la llave privada en Secrets.** El primer intento de deploy falló
  con `error in libcrypto` porque, al copiar la llave privada desde la terminal
  al Secret, se perdieron saltos de línea. OpenSSH exige el formato exacto. Se
  resolvió pegando la llave desde un editor que preserva los saltos de línea.

- **Redundancia del proxy.** nginx sirve su página por defecto en el puerto 80;
  la app corre en el 5000. Fue necesario configurar nginx como proxy inverso y
  deshabilitar el sitio `default` para que el dominio raíz mostrara el
  dashboard en lugar de la página de bienvenida.

- **Inconsistencia de la API ReqRes.** Durante el monitoreo en tiempo real,
  ReqRes alternó entre responder 200 y 401 para la misma petición sin API key,
  confirmando que su validación de credenciales no es uniforme.

## Evidencias

La carpeta de evidencias incluye:

- Dashboard funcionando en la IP pública, con el resumen de servicios activos
  y caídos.
- Pipeline en GitHub Actions con ambos jobs (`test` y `deploy`) en verde.
- Captura del gate en acción: `test` en rojo y `deploy` omitido tras romper una
  prueba a propósito.
- Cambio visual (color del título) reflejado en producción tras un push, sin
  intervención manual en el servidor.
