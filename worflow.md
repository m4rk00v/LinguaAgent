# LinguaAgent — Workflow Completo

## 1. Flujo General del Usuario

```
┌─────────────┐
│   Student    │
│  (Browser)   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────┐
│   Next.js Frontend          │
│   (Tailwind UI)             │
│                             │
│  • Landing / Login          │
│  • Dashboard                │
│  • Chat Interface           │
│  • Voice Interface          │
│  • Progress Reports         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   Auth Layer                │
│   NextAuth + Google OAuth   │
│                             │
│  1. Google OAuth flow       │
│  2. Upsert user in Supabase│
│  3. Issue JWT               │
└──────┬──────────────────────┘
       │ JWT en cada request
       ▼
┌─────────────────────────────┐
│   API Gateway               │
│   (API Routes / FastAPI)    │
│                             │
│  • Valida JWT               │
│  • Identifica tipo de       │
│    sesión (chat/voice)      │
│  • Rutea al agente          │
│    correspondiente          │
└──────┬──────────────────────┘
       │
       ├────────────┬──────────────┐
       ▼            ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────────┐
│ Chat Agent │ │Voice Agent │ │Inspector Agent │
│ (Written)  │ │ (Spoken)   │ │ (Supervisor)   │
└────────────┘ └────────────┘ └────────────────┘
```

---

## 2. Workflow del Chat Agent

```
Student escribe mensaje
       │
       ▼
┌──────────────────────────┐
│ API Gateway              │
│ • Valida JWT             │
│ • Carga últimos N msgs   │
│   desde Redis            │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ RAG Pipeline             │
│ (ver sección 5)          │
│ • Busca contexto del     │
│   estudiante y contenido │
│   relevante              │
└──────┬───────────────────┘
       │ contexto inyectado
       ▼
┌──────────────────────────┐
│ LangChain Agent          │
│ • System prompt +        │
│   RAG context + history  │
│ • Claude API call        │
│ • Tools disponibles:     │
│   - get_student_profile  │
│   - save_session_notes   │
│   - complete_task        │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Post-procesamiento       │
│ • Guarda mensaje en Redis│
│ • Guarda grammar_notes   │
│   en Supabase            │
│ • Notifica al Inspector  │
│   si hay errores nuevos  │
└──────┬───────────────────┘
       │
       ▼
  Respuesta al estudiante
  (texto + nota gramatical)
```

---

## 3. Workflow del Voice Agent

```
Student habla por micrófono
       │
       ▼
┌──────────────────────────┐
│ Whisper (STT)            │
│ • Audio → Texto          │
│ • Target: < 500ms        │
└──────┬───────────────────┘
       │ transcripción
       ▼
┌──────────────────────────┐
│ RAG Pipeline             │
│ • Contexto ligero        │
│   (solo nivel + tema)    │
│ • Optimizado para baja   │
│   latencia               │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ LangChain Agent          │
│ • Prompt de fluency      │
│ • NO corrige en tiempo   │
│   real                   │
│ • Acumula errores        │
│   internamente           │
│ • Claude API call        │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ ElevenLabs (TTS)         │
│ • Texto → Audio          │
│ • Voz natural            │
│ • Target total: < 2s     │
└──────┬───────────────────┘
       │
       ▼
  Audio de respuesta al
  estudiante
       │
       │ (al finalizar sesión)
       ▼
┌──────────────────────────┐
│ Resumen de sesión        │
│ • Errores acumulados     │
│ • Feedback gramatical    │
│ • Guardado en Supabase   │
└──────────────────────────┘
```

---

## 4. Workflow del Inspector Agent

```
┌─────────────────────────────────────────────┐
│            TRIGGERS                         │
│                                             │
│  • Cron diario (tareas pendientes)          │
│  • Cron semanal (reporte de progreso)       │
│  • Webhook post-sesión (Chat/Voice Agent)   │
│  • Stripe webhook (pagos)                   │
└──────┬──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Lógica determinística    │
│ (no necesita LLM)        │
│                          │
│ • Query DB: tareas       │
│   incompletas            │
│ • Query DB: pagos        │
│   vencidos               │
│ • Calcular nivel del     │
│   estudiante basado en   │
│   sesiones + errores     │
│ • Actualizar             │
│   student_profiles       │
└──────┬───────────────────┘
       │
       ├──────── Si hay acciones automáticas ──────┐
       │                                           ▼
       │                                ┌─────────────────────┐
       │                                │ n8n Workflows       │
       │                                │                     │
       │                                │ • Reminder email/WA │
       │                                │ • Suspender acceso  │
       │                                │ • Escalación HITL   │
       │                                └─────────────────────┘
       │
       ├──────── Si es domingo (reporte semanal) ──┐
       │                                           ▼
       │                                ┌─────────────────────┐
       │                                │ LangChain Chain     │
       │                                │                     │
       │                                │ • RAG: perfil +     │
       │                                │   sesiones recientes│
       │                                │ • Claude genera     │
       │                                │   reporte en        │
       │                                │   lenguaje natural  │
       │                                │ • Output Parser →   │
       │                                │   JSON para n8n     │
       │                                └────────┬────────────┘
       │                                         │
       │                                         ▼
       │                                ┌─────────────────────┐
       │                                │ n8n envía reporte   │
       │                                │ por email           │
       │                                └─────────────────────┘
       │
       ├──────── Si detecta anomalía ──────────────┐
       │                                           ▼
       │                                ┌─────────────────────┐
       │                                │ HITL Escalation     │
       │                                │                     │
       │                                │ n8n → Slack/Email   │
       │                                │ Admin revisa        │
       │                                │ Admin aprueba/niega │
       │                                │ n8n ejecuta acción  │
       │                                └─────────────────────┘
       ▼
  Perfil del estudiante actualizado
  en Supabase
```

---

## 5. Pipeline de RAG (detallado)

Este es el núcleo de conocimiento de todos los agentes. Cada vez que un agente necesita contexto, pasa por este pipeline.

### 5.1 Ingesta de datos (offline / batch)

```
┌─────────────────────────────────────────────────────────┐
│                   FUENTES DE DATOS                      │
│                                                         │
│  📄 Contenido de cursos    (lecciones, gramática,       │
│     (markdown, PDF)         vocabulario por nivel)      │
│                                                         │
│  👤 Perfiles de estudiantes (errores frecuentes,        │
│     (actualizado por         temas cubiertos,           │
│      Inspector Agent)        notas de sesiones)         │
│                                                         │
│  📋 Políticas              (precios, planes, TOS)       │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ LangChain Document Loaders               │
│                                          │
│ • PDFLoader (material de cursos)         │
│ • MarkdownLoader (lecciones)             │
│ • Custom loader (student_profiles de DB) │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ LangChain Text Splitters                 │
│                                          │
│ • RecursiveCharacterTextSplitter         │
│ • Chunk size: ~500 tokens                │
│ • Overlap: 50 tokens                     │
│                                          │
│ Estrategia por tipo:                     │
│ ┌──────────────────────────────────────┐ │
│ │ Contenido de cursos:                 │ │
│ │ • 1 chunk por tema/regla gramatical  │ │
│ │ • Metadata: nivel, tema, subtema     │ │
│ ├──────────────────────────────────────┤ │
│ │ Perfil de estudiante:               │ │
│ │ • 1 documento por estudiante        │ │
│ │ • Se re-indexa después de cada      │ │
│ │   sesión (Inspector Agent)          │ │
│ │ • Metadata: user_id, last_updated   │ │
│ ├──────────────────────────────────────┤ │
│ │ Políticas:                          │ │
│ │ • 1 chunk por sección               │ │
│ │ • Metadata: tipo (pricing/tos/plan) │ │
│ └──────────────────────────────────────┘ │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ Generación de Embeddings                 │
│                                          │
│ • Modelo: text-embedding-3-small         │
│ • Dimensiones: 1536                      │
│ • Batch processing para ingesta masiva   │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ Supabase pgvector                        │
│                                          │
│ • Tabla: documents                       │
│   - id                                   │
│   - content (text)                       │
│   - embedding (vector 1536)              │
│   - metadata (jsonb)                     │
│   - source_type (course|profile|policy)  │
│   - created_at                           │
│                                          │
│ • Índice: ivfflat o hnsw                 │
│   para búsqueda rápida                   │
└──────────────────────────────────────────┘
```

### 5.2 Consulta en tiempo real (por cada request del agente)

```
  Agente necesita contexto
  (Chat, Voice o Inspector)
       │
       ▼
┌──────────────────────────────────────────┐
│ 1. Construcción del query                │
│                                          │
│ Input del estudiante + metadata:         │
│ • user_id (para filtrar perfil)          │
│ • agent_type (para ajustar relevancia)   │
│ • nivel actual del estudiante            │
│ • tema de la conversación actual         │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ 2. Query Embedding                       │
│                                          │
│ • text-embedding-3-small                 │
│ • El mensaje del estudiante se convierte │
│   en vector                              │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ 3. Búsqueda semántica en pgvector        │
│                                          │
│ SELECT content, metadata                 │
│ FROM documents                           │
│ WHERE source_type IN (filtros)           │
│   AND metadata->>'level' = student_level │
│ ORDER BY embedding <=> query_embedding   │
│ LIMIT K;                                 │
│                                          │
│ Filtros por agente:                      │
│ ┌────────────────────────────────────┐   │
│ │ Chat Agent:                        │   │
│ │ • K=5                              │   │
│ │ • source: course + profile         │   │
│ │ • Prioriza errores frecuentes      │   │
│ ├────────────────────────────────────┤   │
│ │ Voice Agent:                       │   │
│ │ • K=3 (menos contexto = menos      │   │
│ │   latencia)                        │   │
│ │ • source: course (solo tema)       │   │
│ ├────────────────────────────────────┤   │
│ │ Inspector Agent:                   │   │
│ │ • K=10                             │   │
│ │ • source: profile + todas las      │   │
│ │   sesiones recientes               │   │
│ │ • Para generar reporte completo    │   │
│ └────────────────────────────────────┘   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ 4. Inyección en el prompt                │
│                                          │
│ System prompt del agente:                │
│ ┌────────────────────────────────────┐   │
│ │ You are an English teacher...      │   │
│ │                                    │   │
│ │ ## Student Context                 │   │
│ │ {rag_results[profile]}             │   │
│ │                                    │   │
│ │ ## Relevant Course Material        │   │
│ │ {rag_results[course]}              │   │
│ │                                    │   │
│ │ ## Conversation History            │   │
│ │ {redis_last_n_messages}            │   │
│ └────────────────────────────────────┘   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ 5. LLM Call (Claude API via LangChain)   │
│                                          │
│ • Prompt completo con contexto RAG       │
│ • Respuesta del agente                   │
└──────────────────────────────────────────┘
```

### 5.3 Actualización del perfil (post-sesión)

```
  Sesión finaliza (Chat o Voice)
       │
       ▼
┌──────────────────────────────────────────┐
│ Inspector Agent recibe webhook           │
│                                          │
│ • Lee grammar_notes de la sesión         │
│ • Lee session summary                    │
│ • Actualiza student_profiles en DB       │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Re-indexar perfil en pgvector            │
│                                          │
│ • DELETE embeddings anteriores del       │
│   perfil (WHERE user_id = X AND         │
│   source_type = 'profile')              │
│ • Generar nuevo documento con perfil     │
│   actualizado                            │
│ • Nuevo embedding → INSERT en pgvector   │
└──────────────────────────────────────────┘

El perfil siempre está actualizado para
la siguiente sesión del estudiante.
```

---

## 6. Flujo de Pagos

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Student    │────▶│   Stripe     │────▶│   Webhook    │
│   paga       │     │   Checkout   │     │   endpoint   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                     ┌────────────────────────────┤
                     │                            │
                     ▼                            ▼
              ┌─────────────┐           ┌──────────────┐
              │  Supabase   │           │     n8n      │
              │  payments   │           │              │
              │  table      │           │  Si falla:   │
              │  updated    │           │  • Email     │
              │             │           │  • 7 días →  │
              └─────────────┘           │    suspender │
                                        └──────────────┘
                                                │
                                                ▼
                                        ┌──────────────┐
                                        │   Zapier     │
                                        │              │
                                        │  • Google    │
                                        │    Sheets    │
                                        │    (finanzas)│
                                        └──────────────┘
```

---

## 7. Ciclo de Vida Completo del Estudiante

```
Registro (Google OAuth)
       │
       ▼
Placement test (Chat Agent evalúa nivel inicial)
       │
       ▼
Dashboard con tareas asignadas
       │
       ├──── Clase escrita ──── Chat Agent ──── grammar_notes guardadas
       │
       ├──── Clase oral ──── Voice Agent ──── resumen al final
       │
       ▼
Inspector Agent procesa sesión
       │
       ├──── Actualiza nivel en student_profiles
       ├──── Re-indexa perfil en pgvector
       ├──── Asigna nuevas tareas
       │
       ▼
Cron semanal
       │
       ├──── Inspector genera reporte con RAG
       ├──── n8n envía por email
       │
       ▼
Estudiante ve su progreso → repite ciclo
```
