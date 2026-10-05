# Clave de firma de las actualizaciones (OTA)

Desde la versión 2.4.19 **la placa rechaza cualquier firmware que no esté firmado**
con la clave privada `giddy_ota_signing_key.pem` de esta carpeta
(`CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT`, RSA-3072). El build la usa para
firmar el `.bin` automáticamente.

## Reglas

- **La clave NO va a git** (está en `.gitignore`). Si se filtra, cualquiera puede
  firmar firmware para todos los Giddy.
- **La clave NO se regenera.** Una placa que ya tiene firmware firmado con la clave A
  rechaza para siempre lo firmado con la clave B. Regenerarla = volver a flashear
  todos los equipos por cable.
- Copia de resguardo: en el gestor de contraseñas, como archivo adjunto.

## Pasarla a otra máquina de build (ej. la PC Windows)

Copiala por USB o por el gestor de contraseñas a `firmware/secure/giddy_ota_signing_key.pem`.
Nunca por mail, chat ni git. Sin el archivo, `idf.py build` falla con un error claro.

## Cómo se creó

```bash
espsecure generate-signing-key --version 2 --scheme rsa3072 secure/giddy_ota_signing_key.pem
```

## Verificar que un .bin está firmado

```bash
espsecure verify-signature --version 2 --keyfile secure/giddy_ota_signing_key.pem build/xiaozhi.bin
```

## Primer despliegue

Las placas que hoy corren una versión **sin** verificación (≤ 2.4.18) aceptan la
primera OTA firmada sin problema (no verifican nada). A partir de ahí, solo firmado.
