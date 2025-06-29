import string

class DotDictFormatter(string.Formatter):
    def get_field(self, field_name, _, kwargs):
        obj = kwargs
        for attr in field_name.split("."):
            obj = obj.get(attr) if isinstance(obj, dict) else getattr(obj, attr, None)
            if obj is None:
                break
        return obj, field_name

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, None)
        return super().get_value(key, args, kwargs)
