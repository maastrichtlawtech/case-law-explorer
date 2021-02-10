class CompositeKey:
    def __init__(self, separator='-', **kwargs):
        self.separator = separator
        self.__name = self.separator.join(component for component in kwargs.keys())
        self.__value = self.separator.join(val for val in kwargs.values())
        for component, val in kwargs.items():
            setattr(self, component, val)

    @property
    def name(self):
        return self.__name

    @property
    def value(self):
        return self.__value

    def set_value(self, **kwargs):
        if set(kwargs.keys()) != set(list(self.__dict__.keys())[3:]):
            raise TypeError
        for comp, val in kwargs.items():
            setattr(self, comp, val)
        self.__value = self.separator.join(val for val in list(self.__dict__.values())[3:])


class KeyDocSourceId(CompositeKey):
    def __init__(self, separator='-', doc='', source='', doc_id=''):
        super().__init__(separator=separator, doc=doc, source=source, id=doc_id)

    def set_value(self, doc, source, doc_id):
        super().set_value(doc=doc, source=source, id=doc_id)


class KeySourceDocDate(CompositeKey):
    def __init__(self, separator='-', source='', doc='', date_decision=''):
        super().__init__(separator=separator, source=source, doc=doc, date=date_decision)

    def set_value(self, source, doc, date_decision):
        super().set_value(source=source, doc=doc, date=date_decision)
