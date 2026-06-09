from tools.reference_product_tool import run as run_reference_product


def run(params: dict):
    return run_reference_product(params or {})
