from abc import ABC, abstractmethod


class VectorStore(ABC):
    @abstractmethod
    def init(self, reset: bool = False) -> None: ...

    @abstractmethod
    def upsert(self, rows: list[dict], embeddings: list[list[float]]) -> None: ...

    @abstractmethod
    def search_dense(self, embedding: list[float], k: int) -> list[dict]: ...

    @abstractmethod
    def search_lexical(self, query: str, k: int) -> list[dict]: ...

    @abstractmethod
    def count(self) -> int: ...
