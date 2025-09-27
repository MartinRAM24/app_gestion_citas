-- Tabla de pacientes
CREATE TABLE IF NOT EXISTS pacientes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT now()
);

-- Tabla de citas
CREATE TABLE IF NOT EXISTS citas (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    hora TIME NOT NULL,
    paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
    nota TEXT,
    creado_en TIMESTAMP DEFAULT now(),
    UNIQUE (fecha, hora)  -- evita doble reserva del mismo slot
);
