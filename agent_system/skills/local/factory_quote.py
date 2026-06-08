from tools import factory_quote_tool


def run(params: dict):
    return factory_quote_tool.run(params or {})
