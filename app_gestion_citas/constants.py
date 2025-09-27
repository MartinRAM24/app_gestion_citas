from datetime import time

# Configuración de agenda
HORA_INICIO = time(9, 0)   # 09:00
HORA_FIN = time(17, 0)     # 17:00
PASO_MIN = 30              # minutos entre cada slot
BLOQUEO_DIAS_MIN = 2       # hoy y mañana bloqueados; se puede desde +2 días (día 3)
