from abc import abstractmethod
from typing import TypeVar

T = TypeVar("T")


class StaticCollection:
    @classmethod
    @abstractmethod
    def _item_type(cls) -> type:
        pass

    # NOTE: Unfortunately, using generics to define the return type does not work in IntelliJ; hence private.
    @classmethod
    def _items(cls) -> list:
        items = []
        for _k, v in cls.__dict__.items():
            if isinstance(v, cls._item_type()):
                items.append(v)
        return items
