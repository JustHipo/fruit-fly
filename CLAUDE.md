# Reglas para agentes de IA

Documento corto y a propósito. Manda sobre cualquier hábito por defecto.

## Las reglas no negociables

1. **Leer la documentación primero.** La `ARQUITECTURA.md` del proyecto correspondiente manda sobre cualquier suposición. Si el código y el documento se contradicen, decilo en vez de elegir por tu cuenta.

2. **Regla 0: buscar antes de implementar.** Antes de planificar cualquier implementación, buscar en [docs/avance/REGISTRO_MIGRACIONES.md](docs/avance/REGISTRO_MIGRACIONES.md), recuperar los documentos que aparezcan y leerlos. Declarar en el plan qué se buscó, incluso si no hubo resultados.

3. **El conectoma no se toca.** Es el dato biológico medido. Se entrena el decodificador, nunca el grafo. Cualquier propuesta que modifique la topología medida invalida el proyecto entero.

4. **Nada de decodificadores discontinuos.** Ni hashes, ni funciones que destruyan la relación entre actividad neuronal y salida. Ver la sección 2.3 de art-fly, que documenta el anti-patrón.

5. **Los controles de honestidad no son opcionales.** Ninguna pieza entrenada se da por buena sin el test de cerebro congelado. Ver sección 10 de art-fly.

6. **Declarar lo autoral.** Cada vez que se agrega algo que no sale del conectoma, actualizar la tabla de "lo que es nuestro" del documento del proyecto.

7. **Un commit, una subtask.**

8. **Parar y preguntar.** Ante una decisión de diseño no cubierta por la documentación, preguntar en vez de inventar.

## Lo que podés hacer sin pedir permiso

- Cualquier comando de git de solo lectura (`status`, `diff`, `log`, `branch` listando)
- `git add`, `commit`, `push` **sobre la rama del ticket en curso**, incluidos los trailers de smart commit
- Crear, editar y transicionar issues de Jira del proyecto

## Lo que NO podés hacer sin que te lo pidan en el momento

- Cualquier escritura sobre `main`
- `gh pr create`, `gh pr merge`, `gh release`, `gh repo`
- `push --force`, `reset --hard` sobre trabajo ya pusheado, `rebase` de ramas compartidas
- `branch -D`, `tag -d`, `gc`, `clean`
- Cualquier cosa contra un servidor que no sea localhost
- Borrar archivos de datos descargados (son pesados y caros de recuperar)

## Confirmación de lectura

Antes de recibir la primera tarea, resumir en seis líneas: qué hace cada uno de los dos proyectos, cuál es la restricción de rendimiento que define la arquitectura, por qué la mosca no camina, qué es el test de cerebro congelado, cuál es el formato de commit, y qué está buscando el proyecto que todavía no está resuelto.
