# LUXU AGS — Catálogo + Panel de administración

Sistema local Flask / JSON con catálogo público y panel privado.

## Iniciar (Windows / PowerShell)

```powershell
cd luxu-catalogo
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = 'REEMPLAZA_POR_UNA_CADENA_ALEATORIA_MUY_LARGA'
flask --app app create-admin
python app.py
```

Entra al catálogo: http://127.0.0.1:5000

Panel: http://127.0.0.1:5000/admin

En macOS/Linux reemplaza `py` por `python3`, activa con `source .venv/bin/activate` y exporta `SECRET_KEY`.

**No hay contraseña predeterminada.** El primer usuario se crea con el comando indicado.

## Funciones

- Productos: crear, editar, ocultar, eliminar; SKU, tallas, colores, marca, categoría, existencias, foto principal y galería, precio y precio anterior.
- Marcas, categorías, promociones (% o monto), banners: CRUD desde panel.
- Promociones opcionalmente por artículos específicos, marca o categoría y fechas de vigencia.
- Personalización de portada, imágenes, redes, textos, colores y SEO desde ajustes.
- Carga de imágenes (JPG, PNG, WEBP) convertidas a WEBP.
- Descargar backup ZIP con catálogo y fotografías subidas.
- Cambio de contraseña; contraseña almacenada con hash seguro; sesión y token CSRF.

## Importante

- Los nueve artículos incluidos son **ejemplos ilustrativos**, no inventario real. Elimina o reemplaza todos antes de publicar.
- Guarda la carpeta `data/` para conservar fotos y archivos JSON. `data/` está excluida del ZIP de distribución si contiene datos privados.
- El respaldo ZIP contiene los JSON del catálogo y fotos, pero **no las credenciales**. Para recuperar el sitio completo conserva también `data/users.json` en un lugar seguro.
- Para internet usa HTTPS, configura `COOKIE_SECURE=1`, una `SECRET_KEY` permanente fuerte y despliega detrás de un servidor WSGI (ej. Waitress o Gunicorn). El servidor integrado Flask es solo desarrollo.
- El panel no está diseñado para múltiples administradores simultáneos ni gestión de pedidos o pagos.

## Almacenamiento JSON

No se utiliza SQLite ni ninguna base de datos SQL. Las modificaciones se guardan en `data/products.json`, `data/brands.json`, `data/categories.json`, `data/promotions.json`, `data/banners.json`, `data/settings.json` y `data/users.json`. Las imágenes se almacenan en `data/uploads/`.

Los archivos se crean solos al iniciar. Se utiliza bloqueo por archivo y reemplazo atómico para minimizar corrupción en escrituras simultáneas. No edites manualmente los JSON con la aplicación ejecutándose. `users.json` incluye hashes de contraseña: mantenlo privado y haz copias seguras de toda la carpeta `data/`.

Si tienes datos en una versión anterior con SQLite, esta versión no los migra automáticamente. Antes de sustituir el proyecto, conserva el respaldo de tu instalación anterior.
