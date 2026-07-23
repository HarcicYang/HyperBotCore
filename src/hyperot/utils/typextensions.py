from typing import Union, Optional


class ObjectedJson:
    def __init__(self, content: Optional[Union[dict, list]] = None):
        if content is None:
            self.__content = dict()
        else:
            self.__content = content

    def __getattr__(self, attr):
        if attr == "_ObjectedDict__content" or attr == "raw":
            return self.__content
        else:
            try:
                att = self.__content.get(attr)
            except:
                return None
            if isinstance(att, dict):
                return ObjectedJson(att)
            else:
                return att

    def __setattr__(self, attr, value):
        if attr == "_ObjectedJson__content":
            super().__setattr__(attr, value)
        else:
            try:
                self.__content[attr] = value
            except:
                pass

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
        for i in self.__content:
            yield i

    def __str__(self) -> str:
        return self.__content.__str__()
