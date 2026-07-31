class ObjectedJson:
    def __init__(self, content: dict | list | None = None):
        if content is None:
            self.__content = {}
        else:
            self.__content = content

    def __getattr__(self, attr):
        if attr == "_ObjectedDict__content" or attr == "raw":
            return self.__content
        if not isinstance(self.__content, dict):
            return None
        att = self.__content.get(attr)
        return ObjectedJson(att) if isinstance(att, dict) else att

    def __setattr__(self, attr, value):
        if attr == "_ObjectedJson__content":
            super().__setattr__(attr, value)
        elif isinstance(self.__content, dict):
            self.__content[attr] = value

    def __getitem__(self, item):
        if isinstance(self.__content, dict):
            return self.__content.get(item)
        elif isinstance(self.__content, list):
            return self.__content[item]
        else:
            return None

    def __setitem__(self, key, value):
        self.__content[key] = value

    def __iter__(self):
        yield from self.__content

    def __str__(self) -> str:
        return self.__content.__str__()
