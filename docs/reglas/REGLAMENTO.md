# Reglamento

## Regla 0: buscar antes de implementar

Antes de planificar cualquier implementación, buscar en [../avance/REGISTRO_MIGRACIONES.md](../avance/REGISTRO_MIGRACIONES.md), recuperar los documentos que aparezcan y leerlos. **Declarar en el plan qué se buscó**, aunque no haya habido resultados.

## Reglas de integridad científica

Estas son las que distinguen el proyecto de una demo vacía.

1. **El conectoma no se toca.** Se entrena el decodificador, nunca el grafo medido.
2. **Decodificadores continuos y monótonos.** Ni hashes ni nada que destruya la relación entre actividad y salida.
3. **Test de cerebro congelado obligatorio** sobre toda pieza entrenada.
4. **Controles de topología** (Erdős-Rényi igualado, recableado que preserva grados, permutación de pesos) antes de afirmar que el cableado real importa.
5. **Declarar lo autoral.** Toda pieza que no salga del conectoma va en la tabla correspondiente del documento del proyecto.
6. **Los resultados negativos se publican.** Si el control barajado sale indistinguible, eso se dice. Es un resultado.

## Reglas de proceso

7. **Un commit, una subtask.**
8. **El documento de migración se escribe mientras se implementa**, no después.
9. **Parar y preguntar** ante decisiones no cubiertas por la documentación.

## Permisos de la IA

### Permitido sin pedir
- Git de solo lectura
- `add`, `commit`, `push` sobre la rama del ticket en curso
- Crear, editar y transicionar issues de Jira

### Prohibido sin autorización explícita en el momento
- Cualquier escritura sobre `main`
- `gh pr create|merge|release|repo`
- `push --force`, `reset --hard` sobre trabajo pusheado, `rebase` de ramas compartidas
- `branch -D`, `tag -d`, `gc`, `clean`
- Cualquier cosa contra un servidor que no sea localhost
- Borrar datos descargados del conectoma
