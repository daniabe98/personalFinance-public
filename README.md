# Personal Finance

Aplicación web privada para registrar, consultar y analizar finanzas personales
con rigor contable y una experiencia accesible.

El proyecto se encuentra en fase inicial: todavía no contiene una aplicación
ejecutable. Este repositorio establece su gobierno de ingeniería y conserva una
especificación orientativa que deberá revisarse y aprobarse antes de implementar
el producto.

## Inicio rápido

1. Instala `ai-eng` y las herramientas que indique su diagnóstico.
2. Ejecuta `ai-eng doctor` desde la raíz del repositorio.
3. Comprueba la configuración con `ai-eng check`.

## Instalación

La instalación de la aplicación está pendiente de definir. El stack de
desarrollo configurado actualmente es Python y TypeScript.

## Uso

La aplicación aún no está implementada. El flujo de trabajo del repositorio se
gestiona mediante `ai-eng`; las reglas principales del proyecto se encuentran
en [CONSTITUTION.md](CONSTITUTION.md), y el documento
[especificacion_app_finanzas_personales_v1.md](especificacion_app_finanzas_personales_v1.md)
se utiliza únicamente como orientación para preparar la especificación
canónica.

## Configuración

La configuración de gobierno está en `.ai-engineering/manifest.yml`. Las
superficies generadas por `ai-eng`, incluida `.codex/`, no deben editarse
manualmente.

Antes de trabajar en el producto, consulta también `AGENTS.md` para conocer las
reglas aplicables al repositorio.

## Contribución

Todo cambio debe realizarse en una rama distinta de `main`, seguir los gates de
`ai-eng` y preservar las restricciones de `CONSTITUTION.md`. Antes de proponer
una integración:

```powershell
ai-eng check
ai-eng doctor
```

No deben implementarse decisiones funcionales tomadas únicamente del documento
orientativo sin que hayan pasado al proceso de especificación y aprobación.

## Licencia

TBD. El proyecto todavía no ha definido una licencia.
