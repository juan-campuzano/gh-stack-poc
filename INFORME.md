# Informe de evaluación: `gh-stack` (Stacked Pull Requests de GitHub)

**Fecha de la prueba:** 2026-08-19
**Repositorio de prueba:** https://github.com/juan-campuzano/gh-stack-poc (público)
**Extensión evaluada:** `github/gh-stack` v0.1.0 (extensión oficial de GitHub CLI, `gh extension install github/gh-stack`)
**Documentación oficial:** https://github.github.com/gh-stack/ · https://gh.io/stacks

---

## 1. Resumen ejecutivo

`gh-stack` es una extensión oficial de `gh` (GitHub CLI) que implementa **Stacked Pull Requests**: un flujo de trabajo en el que un cambio grande se divide en una **cadena de PRs pequeños**, cada uno con base en el anterior, en lugar de un único PR gigante contra `main`. GitHub añade soporte nativo para visualizar esa cadena ("stack map") dentro de la interfaz web y para fusionarla de forma atómica.

Se realizó una prueba de concepto robusta y de extremo a extremo: creación de un repositorio público real, construcción de una stack de 4 capas, sincronización tras cambios en una capa intermedia, resolución de un conflicto real de rebase en cascada, y fusión atómica de toda la cadena. **Todos los comandos probados funcionaron según lo documentado, sin errores inesperados de la herramienta.**

**Veredicto corto:** herramienta sólida y bien diseñada para equipos que ya dividen su trabajo en cambios incrementales y quieren automatizar la parte tediosa (rebases en cascada, apertura/actualización de múltiples PRs, merge coordinado). No aporta valor si el equipo trabaja con PRs únicos y no planea adoptar una disciplina de "PRs pequeños encadenados".

---

## 2. Qué es y qué problema resuelve

Los PRs grandes son difíciles de revisar (pierden contexto, generan comentarios superficiales) y son propensos a conflictos de merge cuando tardan en revisarse. La alternativa habitual — dividir el cambio en varios PRs — tradicionalmente es dolorosa a mano:

- Cada PR depende del anterior (base branch != `main`), y GitHub no visualizaba bien esa relación.
- Cuando el PR #1 cambia (por una revisión), hay que rebasear manualmente el #2, #3, #4… y volver a hacer force-push a cada uno.
- Fusionar la cadena requiere mergear uno por uno, en orden, actualizando bases a mano.

`gh-stack` automatiza las tres partes: creación/gestión local de la cadena de branches, sincronización/rebase en cascada, y fusión atómica de la stack completa (todo o nada).

---

## 3. Instalación

```bash
gh extension install github/gh-stack
gh stack alias        # opcional: crea el atajo `gs`
```

**Nota de entorno encontrada durante la prueba:** en macOS, si `$HOME/.local/share` no es escribible por el usuario (permisos root en instalaciones gestionadas o corporativas), la instalación falla con `permission denied`. Solución: exportar `XDG_DATA_HOME` a un directorio propio antes de instalar. No es un defecto de la herramienta, pero conviene documentarlo para equipos con máquinas gestionadas centralmente.

Verificación de versión:
```
$ gh extension list
gh stack   github/gh-stack   v0.1.0
```

---

## 4. Metodología de la prueba

Se simuló un caso realista: implementar una "API de usuarios" dividida en 4 capas lógicas, tal como se recomienda dividir un cambio grande:

| Capa | Branch | Contenido |
|---|---|---|
| 1 | `feature/1-schema` | Esquema SQL de la tabla `users` |
| 2 | `feature/2-model` | Modelo de datos Python (`User`) |
| 3 | `feature/3-endpoints` | Endpoint FastAPI que usa el modelo |
| 4 | `feature/4-docs` | Documentación del endpoint |

Pasos ejecutados (todos contra un repo público real, no un sandbox simulado):

1. `gh stack init feature/1-schema` → primer commit.
2. `gh stack add feature/2-model`, `add feature/3-endpoints`, `add feature/4-docs` → un commit por capa.
3. `gh stack submit --auto --open` → creación de los 4 PRs reales en GitHub.
4. Verificación de las bases de cada PR vía `gh pr view --json baseRefName`.
5. Cambio en la capa 1 (`feature/1-schema`) + `gh stack sync` → verificar propagación en cascada.
6. **Prueba de conflicto real**: edición de la misma línea del mismo archivo en dos capas distintas (`feature/2-model` y `feature/3-endpoints`) para forzar un conflicto de rebase real, no simulado.
7. Resolución del conflicto con `gh stack rebase` / `--continue`, verificando el estado del árbol git durante el proceso.
8. Navegación con `up` / `down` / `top` / `bottom`.
9. `gh stack merge --yes --merge` → fusión atómica de los 4 PRs.
10. `gh stack sync --prune` → limpieza automática de branches locales tras el merge.

---

## 5. Resultados detallados

### 5.1 Creación de la stack (`init` / `add`)

```
✓ Created stack: main ← feature/1-schema
```

Cada `gh stack add <branch>` crea el branch encima del branch actual de la stack y lo registra en metadata local. `gh stack view` en cualquier momento muestra un árbol ASCII claro:

```
● feature/4-docs (current)
│ Add API documentation
○ feature/3-endpoints
│ Add users API endpoint
○ feature/2-model
│ Add User data model
○ feature/1-schema
│ Add users table schema
└ main
```

### 5.2 Publicación (`submit`)

`gh stack submit --auto --open` empujó los 4 branches y creó 4 PRs reales en un solo comando, encadenando automáticamente las bases:

| PR | Head | Base |
|---|---|---|
| #1 | `feature/1-schema` | `main` |
| #2 | `feature/2-model` | `feature/1-schema` |
| #3 | `feature/3-endpoints` | `feature/2-model` |
| #4 | `feature/4-docs` | `feature/3-endpoints` |

Esto es exactamente lo que se haría a mano con `gh pr create --base <branch-anterior>`, pero en un solo comando y sin errores de tipeo en los nombres de base.

### 5.3 Sincronización tras cambio en capa intermedia (`sync`)

Se añadió una tabla `posts` en `feature/1-schema` (la capa más baja) y se ejecutó `gh stack sync`. Resultado:

```
✓ Rebased feature/1-schema onto main
✓ Rebased feature/2-model onto feature/1-schema
✓ Rebased feature/3-endpoints onto feature/2-model
✓ Rebased feature/4-docs onto feature/3-endpoints
✓ Pushed 4 branches
✓ Stack on GitHub is up to date with 4 PRs (stack #5)
```

Un solo comando reescribió y volvió a empujar (con `--force-with-lease --atomic`, según su propia documentación) las 4 ramas manteniendo la cadena consistente, y sincronizó el estado de los PRs. Esto reemplaza lo que normalmente serían 4 rebases manuales + 4 force-push + revisar que ningún PR quedara con base rota.

### 5.4 Conflicto real de rebase (`rebase` / `--continue` / `--abort`)

Se forzó deliberadamente un conflicto editando la misma línea de `src/model.py` en `feature/2-model` y en `feature/3-endpoints`. Al sincronizar:

```
✓ Rebased feature/1-schema onto main
✓ Rebased feature/2-model onto feature/1-schema
✗ Conflict detected rebasing feature/3-endpoints onto feature/2-model
  All branches restored to their original state.
  Run `gh stack rebase` to resolve conflicts interactively.
```

**Punto fuerte notable:** ante un conflicto, `gh stack sync` **revierte automáticamente todo a su estado original** (no deja el repo a medio rebasear) y remite a `gh stack rebase`. Este último entra en un `git rebase` interactivo estándar:

```
Conflicted files:
  C src/model.py
...
Resolve conflicts on feature/3-endpoints, then run `gh stack rebase --continue`
Or abort this operation with `gh stack rebase --abort`
```

La resolución fue idéntica a un conflicto de `git rebase` normal (marcadores `<<<<<<<`/`=======`/`>>>>>>>`, `git add`, continuar). Tras `--continue`, la herramienta retomó automáticamente el rebase en cascada de las capas restantes (`feature/4-docs`) sin intervención adicional. No hay "magia" oculta ni un formato propietario de resolución de conflictos — es Git puro con una capa de orquestación encima, lo cual es tranquilizador desde el punto de vista de confiabilidad.

### 5.5 Navegación (`up` / `down` / `top` / `bottom`)

```
$ gh stack bottom   → feature/1-schema
$ gh stack up       → feature/2-model
$ gh stack top      → feature/4-docs
$ gh stack down     → feature/3-endpoints
```

Funcionan como se espera; útil para moverse rápido por la cadena sin recordar nombres de branches.

### 5.6 Merge atómico (`merge`)

```
$ gh stack merge --yes --merge
Merging #1, #2, #3, #4 into main via merge...
✓ Merged #1, #2, #3, #4 into main (b247f81)
```

Los 4 PRs pasaron a estado `MERGED` en GitHub en una sola operación "todo o nada": si alguno hubiera fallado (por ejemplo, por una regla de protección de rama), la documentación indica que ninguno se fusiona. El historial de `main` quedó con los commits originales de cada capa preservados dentro del merge commit final, no aplastados en uno solo.

### 5.7 Limpieza (`sync --prune`)

```
✓ Pruned feature/1-schema (merged)
✓ Pruned feature/2-model (merged)
✓ Pruned feature/3-endpoints (merged)
✓ Pruned feature/4-docs (merged)
```

Tras el merge, un solo comando detectó qué branches ya estaban fusionados y los borró localmente, dejando el working tree limpio (`git branch -a` → solo `main`).

---

## 6. Ventajas

1. **Automatiza el dolor real de los PRs encadenados**: rebase en cascada, force-push coordinado y actualización de bases, que de otro modo son 100% manuales y propensos a error humano (base branch incorrecto, olvidar force-push a un PR intermedio, etc.).
2. **Es Git puro por debajo**: los conflictos se resuelven con el flujo estándar de `git rebase` (marcadores, `git add`, `--continue`/`--abort`). No hay que aprender un modelo de conflictos propietario.
3. **Rollback automático y seguro ante conflictos**: `sync` nunca deja el repo en un estado intermedio roto; siempre revierte a un punto conocido antes de pedir intervención manual.
4. **Merge atómico "todo o nada"**: evita el escenario de fusionar 3 de 4 PRs y quedar con una base rota a medio camino.
5. **Integración nativa con GitHub** (no solo local): las bases de los PRs, el "stack map" en la UI, y las reglas de protección de rama se aplican correctamente sobre la rama final, no solo la inmediata — según la documentación.
6. **Diffs de PR acotados**: cada PR en GitHub muestra solo el diff de su propia capa (verificado con `gh pr diff 3`), no el acumulado de las capas anteriores, que es justamente el beneficio de fondo (revisiones más enfocadas).
7. **Complementa, no reemplaza, el flujo git/gh existente**: los comandos son atajos sobre operaciones git estándar (branch, rebase, push --force-with-lease), por lo que el equipo no queda atado a un formato de metadata irrecuperable si se abandona la herramienta.
8. **CLI ergonómica**: mensajes de estado claros con checkmarks, sugerencias del "próximo comando" tras cada operación, y un `gh stack view` legible en cualquier momento.

## 7. Desventajas / riesgos

1. **Curva de coordinación en equipo**: la herramienta es fuerte en el flujo *individual* (una persona construyendo su propia stack), pero si dos personas necesitan tocar la misma stack, o si alguien hace push manual a una rama intermedia sin pasar por `gh stack`, el estado local puede divergir del remoto y requerir resolución manual (la propia documentación de `sync` lo advierte explícitamente: "prompts to use the remote as the source of truth").
2. **Dependencia de la extensión y de GitHub**: el "stack" como objeto de primera clase vive en GitHub (vinculado a través de la extensión); moverse a otro forge (GitLab, Bitbucket) no preserva ese concepto, aunque los branches y PRs subyacentes seguirían siendo git estándar.
3. **Herramienta joven (v0.1.0)**: al momento de la prueba es una versión temprana. No se encontraron bugs en esta prueba, pero el historial de versión sugiere que el comportamiento (flags, mensajes, límites) puede cambiar.
4. **Requiere disciplina de branching**: obliga a pensar el cambio en capas *antes* de programar, o al menos a reorganizar el trabajo en capas después (existe `gh stack modify` para reestructurar, no probado aquí a fondo). Para gente acostumbrada a un único commit/PR por feature, hay fricción de hábito.
5. **Force-push como operación rutinaria**: cada `sync`/`rebase` reescribe historia y hace force-push (con `--force-with-lease`, que es la variante segura, pero sigue siendo force-push). Equipos con políticas estrictas de "nunca force-push" deben adaptar esa política para las ramas de la stack.
6. **Merge atómico depende de reglas de protección de rama**: si el repo tiene checks de CI obligatorios por PR, cada capa debe pasarlos individualmente para que el merge atómico funcione; en un repo con checks lentos, esto puede ser más lento que mergear un PR único.
7. **No sustituye la revisión de diseño**: divide el *código* en capas, pero si el diseño general del cambio es incorrecto, dividirlo en 4 PRs solo reparte el problema en 4 sitios en vez de resolverlo.

## 8. Curva de aprendizaje

- **Para quien ya usa `gh` CLI y entiende rebase**: **baja**. Los nombres de comando son intuitivos (`init`, `add`, `submit`, `sync`, `merge`) y siguen el vocabulario ya establecido por otras herramientas de stacking como Graphite o `git-branchless`. En esta prueba, los primeros comandos funcionaron correctamente al primer intento leyendo solo `--help`.
- **Para quien no está cómodo con `git rebase` y conflictos**: **media-alta**. La herramienta automatiza la orquestación, pero cuando aparece un conflicto real (como se forzó en esta prueba), termina exigiendo resolver un conflicto de rebase manual estándar de Git. Si el equipo no domina eso, la herramienta no elimina esa necesidad, solo reduce cuántas veces hay que hacerlo manualmente.
- **Para equipos**: la parte no trivial no es aprender los comandos, sino **adoptar la disciplina** de planear el cambio en capas pequeñas y revisarlas en orden — eso es un cambio de proceso, no solo de herramienta.
- Tiempo estimado hasta productividad razonable: **1–2 horas** de práctica guiada para un desarrollador con experiencia en Git intermedia/avanzada; **medio día** si además hay que interiorizar el hábito de dividir el trabajo en capas.

## 9. Recomendaciones

1. **Adoptarla si**: el equipo ya sufre con PRs grandes y lentos de revisar, o ya practica "trunk-based development con cambios incrementales" pero lo hace a mano hoy. El ROI es alto porque automatiza exactamente la parte tediosa y propensa a error (rebases en cascada, bases de PR).
2. **No forzarla si**: el equipo trabaja con features aisladas de bajo acoplamiento donde un PR por feature ya es pequeño y autocontenido — no hay "cambio grande" que dividir, y la herramienta añadiría complejidad sin beneficio.
3. **Probar primero en un repo satélite o de bajo riesgo** (como se hizo aquí) antes de adoptarla en el repositorio principal del producto, dado que es v0.1.0 y las políticas de force-push/protección de ramas deben ajustarse.
4. **Definir una convención de nombres de branch para las capas** (`feature/<n>-<slug>` funcionó bien en la prueba) para que `gh stack view` sea legible en stacks largas.
5. **Combinar con checks de CI rápidos por PR**: dado que el merge atómico depende de que cada capa individual pase sus checks, checks lentos o flaky penalizan más en este flujo que en un PR único.
6. **Capacitar al equipo en resolución de conflictos de rebase estándar** antes de adoptar la herramienta — es la única parte que no se automatiza y es donde se pierde más tiempo si no se domina.
7. **Revisar `gh stack modify`** (no cubierto en profundidad en esta prueba) antes de adoptar, ya que reestructurar una stack existente (reordenar, dividir, fusionar capas) es una operación frecuente en la práctica y vale la pena entender sus límites de antemano.

## 10. Evidencia (repositorio de la prueba)

- Repositorio público: https://github.com/juan-campuzano/gh-stack-poc
- PRs de la stack (todos `MERGED`): [#1](https://github.com/juan-campuzano/gh-stack-poc/pull/1) · [#2](https://github.com/juan-campuzano/gh-stack-poc/pull/2) · [#3](https://github.com/juan-campuzano/gh-stack-poc/pull/3) · [#4](https://github.com/juan-campuzano/gh-stack-poc/pull/4)
- Historial de `main` tras el merge conserva los commits individuales de cada capa dentro del merge commit final.

## 11. Conclusión

`gh-stack` cumple lo que promete: convierte el flujo manual y propenso a errores de PRs encadenados en un puñado de comandos confiables, construidos sobre operaciones Git estándar (por lo que no genera vendor lock-in real). La prueba, incluyendo un conflicto de rebase forzado deliberadamente, no reveló comportamientos inesperados ni pérdida de trabajo. Es una herramienta recomendable para equipos que ya practican — o quieren empezar a practicar — cambios grandes divididos en capas pequeñas y revisables; no aporta valor si ese no es el flujo de trabajo del equipo.
