from data_to_dynamodb.components.types import validate_source, validate_doctype, validate_date


class Key:
    def __init__(self, separator='_', **kwargs):
        self.separator = separator
        self.__name = self.separator.join(component for component in kwargs.keys())
        self.__value = self.separator.join(val for val in kwargs.values())

    @property
    def name(self):
        return self.__name

    @property
    def value(self):
        return self.__value

    def set_value(self, **kwargs):
        values = []
        for component in self.name.split(self.separator):
            if component not in kwargs.keys():
                print(f'{self.name}, {kwargs.keys()}')
                raise TypeError
            values.append(kwargs[component])
        self.__value = self.separator.join(values)
        return {self.name: self.value}


class KeyDocSourceId(Key):
    """
    format: <doc_type-source-doc_id>
    example: DEC-RS-ECLI:NL:HR:1234
    """
    def __init__(self, separator='_', doc_type='', source='', doc_id=''):
        source = validate_source(source)
        doc_type = validate_doctype(doc_type)
        super().__init__(separator=separator, doc=doc_type, source=source, id=doc_id)

    def set_value(self, doc_type, source, doc_id):
        source = validate_source(source)
        doc_type = validate_doctype(doc_type)
        return super().set_value(doc=doc_type, source=source, id=doc_id)


class KeySourceDocDate(Key):
    """
    format: <source-doc_type-date_decision>
    example: RS-DEC-2021-02-07
    """
    def __init__(self, separator='_', source='', doc_type='', date_decision=''):
        source = validate_source(source)
        doc_type = validate_doctype(doc_type)
        date_decision = validate_date(date_decision)
        super().__init__(separator=separator, source=source, doc=doc_type, date=date_decision)

    def set_value(self, source, doc_type, date_decision):
        source = validate_source(source)
        doc_type = validate_doctype(doc_type)
        return super().set_value(source=source, doc=doc_type, date=date_decision)
