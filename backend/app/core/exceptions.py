class InvalidRagRequestError(ValueError):
    """Exception raised when RAG request validation fails (e.g. empty or invalid parameters)."""
    pass


class DocumentNotFoundError(LookupError):
    """Exception raised when the requested document does not exist."""
    pass


class RetrievalUnavailableError(RuntimeError):
    """Exception raised when the retrieval database cannot serve requests due to data inconsistency."""
    pass
