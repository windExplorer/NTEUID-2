class MessageSegment:
    @staticmethod
    def image(*args, **kwargs):
        return "image"

    @staticmethod
    def text(*args, **kwargs):
        return "text"

    @staticmethod
    def node(*args, **kwargs):
        return "node"
