# Demo estática (Netlify)

Esto **no es la app real**. Es una copia del panel con datos de mentira en memoria
(sin servidor, sin agentes, sin login real, sin publicar nada), solo para enseñar
el diseño visual del login y del chat.

La app de verdad vive en `factory/panel.py` + `factory/panel.html` y necesita un
servidor Python corriendo en el ordenador de cada socio (`python factory.py panel`
o `ABRIR_PANEL.bat`). Esa parte no se puede desplegar en Netlify: lee y escribe
archivos locales (libros, chat, PINs) y mantiene una conexión en directo.
