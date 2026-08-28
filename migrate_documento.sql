-- Migracion: Agregar campo documento a tabla usuarios
-- Ejecutar en Supabase SQL Editor

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS documento TEXT;

CREATE INDEX IF NOT EXISTS idx_usuarios_documento ON usuarios(documento);

CREATE TABLE IF NOT EXISTS llamadas (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    usuario_email TEXT,
    usuario_nombre TEXT,
    documento TEXT,
    duracion_segundos INTEGER,
    paso_final TEXT,
    estado TEXT DEFAULT 'completada',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llamadas_email ON llamadas(usuario_email);
