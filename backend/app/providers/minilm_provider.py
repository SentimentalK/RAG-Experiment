from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

class MiniLMProvider:
    """
    Provider for sentence embeddings using sentence-transformers/all-MiniLM-L6-v2.
    Forces CPU utilization and executes L2 normalization on generated vectors.
    """
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EXPECTED_DIMENSIONS = 384

    def __init__(self, device: str = "cpu") -> None:
        self._model = SentenceTransformer(
            self.MODEL_NAME,
            device=device,
        )

    @property
    def model_name(self) -> str:
        return self.MODEL_NAME

    @property
    def dimensions(self) -> int:
        dimension = self._model.get_embedding_dimension()

        if dimension != self.EXPECTED_DIMENSIONS:
            raise RuntimeError(
                f"Expected {self.EXPECTED_DIMENSIONS} dimensions, "
                f"but model returned {dimension}."
            )

        return dimension

    @property
    def max_sequence_length(self) -> int:
        return self._model.get_max_seq_length()

    def count_tokens(self, text: str) -> int:
        """
        Counts the number of tokens in the text using the model's tokenizer.
        """
        token_ids = self._model.tokenizer.encode(
            text,
            add_special_tokens=True,
            truncation=False
        )
        return len(token_ids)

    def encode(self, text: str) -> np.ndarray:
        """
        Generates a 384-dimensional normalized embedding for a given text.
        """
        if not isinstance(text, str):
            raise TypeError("Embedding input must be a string.")

        if not text.strip():
            raise ValueError("Embedding input cannot be empty.")

        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        result = np.asarray(embedding, dtype=np.float32)
        self._validate_embedding(result)

        return result

    def _validate_embedding(self, embedding: np.ndarray) -> None:
        expected_shape = (self.EXPECTED_DIMENSIONS,)

        if embedding.shape != expected_shape:
            raise ValueError(
                f"Expected embedding shape {expected_shape}, "
                f"received {embedding.shape}."
            )

        if embedding.dtype != np.float32:
            raise ValueError(
                f"Expected float32 embedding, received {embedding.dtype}."
            )

        if not np.isfinite(embedding).all():
            raise ValueError(
                "Embedding contains NaN or infinite values."
            )

        norm = float(np.linalg.norm(embedding))

        if not np.isclose(norm, 1.0, atol=1e-5):
            raise ValueError(
                f"Expected normalized embedding, received norm {norm:.8f}."
            )

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Generates 384-dimensional normalized embeddings for a batch of texts.
        """
        if not texts:
            raise ValueError("Embedding input list cannot be empty.")

        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"Text at index {index} must be a string."
                )
            if not text.strip():
                raise ValueError(
                    f"Text at index {index} cannot be empty."
                )

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

        result = np.asarray(embeddings, dtype=np.float32)
        self._validate_embedding_batch(result, expected_count=len(texts))

        return result

    def _validate_embedding_batch(self, embeddings: np.ndarray, expected_count: int) -> None:
        expected_shape = (expected_count, self.EXPECTED_DIMENSIONS)

        if embeddings.shape != expected_shape:
            raise ValueError(
                f"Expected embedding matrix shape {expected_shape}, "
                f"received {embeddings.shape}."
            )

        if embeddings.dtype != np.float32:
            raise ValueError(
                f"Expected float32 matrix, received {embeddings.dtype}."
            )

        if not np.isfinite(embeddings).all():
            raise ValueError(
                "Embedding matrix contains NaN or infinite values."
            )

        norms = np.linalg.norm(embeddings, axis=1)

        if not np.allclose(norms, 1.0, atol=1e-5):
            invalid_count = int(
                np.count_nonzero(
                    ~np.isclose(norms, 1.0, atol=1e-5)
                )
            )
            raise ValueError(
                f"{invalid_count} embeddings are not normalized."
            )
