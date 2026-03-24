# LinguaAgent — Setup

## Ollama (LLM local gratuito)

### Instalar Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Descargar modelos
```bash
ollama pull llama3           # LLM para los agentes
ollama pull nomic-embed-text # embeddings para RAG (768 dimensiones)
```

### Verificar
```bash
ollama list
```

---

# Supabase CLI — Setup & Migraciones

## 1. Login
```bash
npx supabase login
```

## 2. Vincular proyecto
```bash
npx supabase link --project-ref <tu-reference-id>
```
El **Reference ID** se encuentra en: Dashboard de Supabase → Settings → General → Reference ID.

## 3. Ejecutar migraciones
```bash
npx supabase db push
```

## 4. Verificar estado
```bash
npx supabase db status
```

---

## Migraciones aplicadas

| # | Archivo | Descripción |
|---|---------|-------------|
| 1 | `20260323000001_create_tables.sql` | Tablas relacionales (users, sessions, tasks, etc.) |
| 2 | `20260323000002_enable_pgvector.sql` | Extensión pgvector + tabla documents |
| 3 | `20260323000003_search_function.sql` | Función match_documents para búsqueda semántica |
| 4 | `20260323000004_seed_data.sql` | Datos de ejemplo (3 usuarios, sesiones, tareas, etc.) |
| 5 | `20260323000005_update_vector_dimensions.sql` | Cambio VECTOR(1536) → VECTOR(768) para Ollama nomic-embed-text |
