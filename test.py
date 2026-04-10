import polaris_time 
from datetime import datetime, timezone

now = datetime.now(timezone.utc)

# Exemple : France Paris
longitude = 2.33333

polaris_hour = polaris_time.polaris_hour_angle(now, longitude)

print(polaris_hour, polaris_time.lst(now, longitude))

