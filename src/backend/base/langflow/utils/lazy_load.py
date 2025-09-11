class LazyLoadDictBase:
    def __init__(self) -> None:
        self._all_types_dict = None

    @property
    def all_types_dict(self):
        if self._all_types_dict is None:
            self._all_types_dict = self._build_dict()
        return self._all_types_dict

    def _build_dict(self):
        raise NotImplementedError

    def get_type_dict(self):
        raise NotImplementedError
