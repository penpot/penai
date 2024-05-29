from collections.abc import Callable


def apply_func_to_nested_keys(d: dict, func: Callable) -> dict:
    """Apply a function to all nested keys in a dictionary."""
    new_d = {}
    for k, v in d.items():
        new_k = func(k)
        if isinstance(v, dict):
            new_d[new_k] = apply_func_to_nested_keys(v, func)
        else:
            new_d[new_k] = v
    return new_d
