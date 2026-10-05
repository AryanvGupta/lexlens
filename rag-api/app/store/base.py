from abc import ABC, abstractmethod


class VectorStore(ABC):
    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def upsert(self, rows: list[dict], embeddings: list[list[float]]) -> None: ...

    @abstractmethod
    def search_dense(self, embedding: list[float], k: int) -> list[dict]: ...

    @abstractmethod
    def count(self) -> int: ...
