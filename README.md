# App de Citas – Gestor de Agenda para Clientes

Aplicación web para gestionar citas de forma sencilla y rápida.  
Pensada para profesionales que necesitan agendar y organizar sus sesiones con clientes de manera ordenada (por ejemplo, entrenadores, nutriólogos, terapeutas, etc.).

---

## 🧩 Funcionalidades principales

- 📅 **Crear, editar y eliminar citas**
- 👤 **Gestión básica de clientes** (nombre, contacto)
- ⏰ **Filtro por fecha y rango de horas**
- 🔍 **Búsqueda de citas por nombre de cliente**
- ✅ Indicadores de estado de la cita (pendiente, realizada, cancelada)
- 🧱 Panel simple e intuitivo pensado para uso diario

---

## 🛠️ Tecnologías utilizadas

- Python
- Streamlit
- PostgreSQL (Neon / cualquier instancia compatible)
- SQLAlchemy / psycopg2 (según implementación)
- Docker (opcional, para despliegue)
- Railway / similar (para hosting, opcional)

---

## ✅ Requisitos previos

- Python 3.10+
- Cuenta en PostgreSQL (Neon u otro proveedor)
- (Opcional) Docker instalado
- (Opcional) Cuenta en Railway u otro servicio de despliegue

---

## 🔐 Variables de entorno

Crear un archivo `.env` en la raíz del proyecto con algo similar:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DB_NAME
SECRET_KEY=una_clave_secreta_larga
ADMIN_USER=admin
ADMIN_PASSWORD=admin_password_seguro
PEPPER=pepper_para_hash
ENV=production
