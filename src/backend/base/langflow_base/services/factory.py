class ServiceFactory:
    def __init__(self, service_class):
        self.service_class = service_class

    def create(self, *args, **kwargs):
        raise NotImplementedError
