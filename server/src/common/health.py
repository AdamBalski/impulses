import enum

class HealthStatus(str, enum.Enum):
    UP = "UP"
    INITIALIZING = "INITIALIZING"
    STOPPING = "STOPPING"
class AppHealth:
    def __init__(self, status: HealthStatus):
        self.status = status
