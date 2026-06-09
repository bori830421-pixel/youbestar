from tools.business_records_tool import run as run_business_records


def run(params: dict):
    return run_business_records(params or {})
