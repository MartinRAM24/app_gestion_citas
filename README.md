# App de citas para salón de belleza

Aplicación en **Streamlit** para gestionar citas por hora para un local de belleza.
Incluye dos perfiles:

- **Cliente**: registro/inicio de sesión, agendar cita con tipo de servicio y ver su próxima cita.
- **Administradora (dueña)**: crear, editar, eliminar y revisar citas, además de ver una notificación de la última cita agendada.

## Funcionalidades

- Registro e inicio de sesión de clientes.
- Agenda por bloques horarios.
- Selección de **tipo de servicio** al agendar.
- Vista de próxima cita del cliente.
- Panel admin para gestión completa de citas.
- Indicador/notificación de la **última cita agendada**.
- Integración opcional de recordatorios por WhatsApp.

## Stack

- Python 3.10+
- Streamlit
- PostgreSQL (Neon)
- psycopg3
- Railway para despliegue

## Variables de entorno

Configura estas variables en Railway (o en local):

- `NEON_DATABASE_URL` (cadena de conexión de Neon)
- `ADMIN_USER` (ej. `Carmen`)
- `ADMIN_PASSWORD`
- `PASSWORD_PEPPER` (opcional)

Opcionales para WhatsApp (en `st.secrets["whatsapp"]`):

- `PHONE_NUMBER_ID`
- `TOKEN`
- `TEMPLATE`
- `LANG`

## Ejecutar local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run Home.py
```

## Despliegue en Railway

1. Sube este repositorio a GitHub.
2. En Railway crea un proyecto y conecta el repo.
3. Añade las variables de entorno indicadas arriba.
4. Railway detectará el `Procfile` y levantará Streamlit.
5. Verifica que la URL pública cargue el login.

## Notas de BD

El esquema se crea automáticamente al iniciar la app y agrega la columna `servicio` si no existe.
