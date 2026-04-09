import polaris_time 
from datetime import datetime, timezone

now = datetime.now(timezone.utc)

# Exemple : France (~2° Est)
longitude = 2.532330

polaris_hour = polaris_time.polaris_hour_angle(now, longitude)

print(polaris_hour, polaris_time.lst(now, longitude))
