class OrchestratorBaseException(Exception):
    def __init__(self, message: str, service_name: str = "unknown", details: dict = None):
        self.message = message
        self.service_name = service_name
        self.details = details or {}
        super().__init__(self.message)

class ServiceUnavailableError(OrchestratorBaseException):
    pass

class ServiceProcessingError(OrchestratorBaseException):
    pass