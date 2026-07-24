class GSC:
    def __init__(self, name, help_text, data, *args, **kwargs):
        self.name = name
        self.help = help_text
        self.data = data
        self.options = kwargs.get("options")


class GsIntConfig(GSC):
    pass


class GsStrConfig(GSC):
    pass


class GsBoolConfig(GSC):
    pass


class GsListConfig(GSC):
    pass


class GsTimeConfig(GSC):
    pass


class GsListStrConfig(GSC):
    pass


class GsTimeRConfig(GSC):
    pass
