-- ================================================
-- SCHEMA: Base de datos TusAbogados.com
-- Supabase (PostgreSQL)
-- Ejecutar en SQL Editor de Supabase Dashboard
-- ================================================

-- ── Tabla: usuarios ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    telefono TEXT,
    documento TEXT,
    rol TEXT,                    -- 'demandado' o 'demandante'
    categoria TEXT,              -- 'civil', 'laboral', 'penal', 'no_definida'
    descripcion_caso TEXT,
    tiene_pruebas BOOLEAN DEFAULT FALSE,
    paso_actual TEXT DEFAULT 'saludo_inicial',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ── Tabla: usuarios ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS citas (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    usuario_email TEXT NOT NULL,
    usuario_nombre TEXT,
    usuario_telefono TEXT,
    categoria TEXT,
    descripcion_caso TEXT,
    fecha_cita DATE NOT NULL,
    hora_cita TEXT NOT NULL,        -- '09:00', '10:30', etc.
    estado TEXT DEFAULT 'confirmada', -- 'confirmada', 'reprogramada', 'cancelada', 'completada'
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tabla: conversaciones ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversaciones (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    usuario_email TEXT,
    usuario_nombre TEXT,
    mensaje_usuario TEXT,
    respuesta_agente TEXT,
    paso TEXT,                      -- paso del guion en el que estaba
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tabla: consultas_adicionales ────────────────────────────────────
CREATE TABLE IF NOT EXISTS consultas_adicionales (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    usuario_email TEXT NOT NULL,
    usuario_nombre TEXT,
    consulta TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Índices para búsquedas rápidas ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_citas_email ON citas(usuario_email);
CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas(fecha_cita);
CREATE INDEX IF NOT EXISTS idx_citas_estado ON citas(estado);
CREATE INDEX IF NOT EXISTS idx_conversaciones_email ON conversaciones(usuario_email);
CREATE INDEX IF NOT EXISTS idx_consultas_email ON consultas_adicionales(usuario_email);

-- ── RLS (Row Level Security) - Opcional ─────────────────────────────
-- Habilitar si se usa autenticación con Supabase Auth
-- ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE citas ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conversaciones ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE consultas_adicionales ENABLE ROW LEVEL SECURITY;

-- ── Vista resumen de citas ──────────────────────────────────────────
CREATE OR REPLACE VIEW vista_citas_pendientes AS
SELECT
    c.id,
    c.usuario_nombre,
    c.usuario_email,
    c.usuario_telefono,
    c.categoria,
    c.fecha_cita,
    c.hora_cita,
    c.estado,
    c.created_at
FROM citas c
WHERE c.estado IN ('confirmada', 'reprogramada')
ORDER BY c.fecha_cita ASC, c.hora_cita ASC;

-- ── Vista de estadísticas ───────────────────────────────────────────
CREATE OR REPLACE VIEW vista_estadisticas AS
SELECT
    (SELECT COUNT(*) FROM usuarios) AS total_usuarios,
    (SELECT COUNT(*) FROM citas WHERE estado = 'confirmada') AS citas_pendientes,
    (SELECT COUNT(*) FROM citas WHERE estado = 'completada') AS citas_completadas,
    (SELECT COUNT(*) FROM conversaciones) AS total_conversaciones;

-- ================================================
-- FIN DEL SCHEMA
-- ================================================