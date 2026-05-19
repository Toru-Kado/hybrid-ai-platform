"""OpenSearch client for full-text message search.

Uses SigV4 authentication for OpenSearch Serverless access.
Provides search, index, and delete operations scoped by user.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """Client for OpenSearch Serverless collection.

    Uses the opensearch-py library with SigV4 auth for serverless access.
    Falls back gracefully if OpenSearch is not configured.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        index_name: str | None = None,
    ) -> None:
        self._endpoint = endpoint or os.environ.get("OPENSEARCH_ENDPOINT", "")
        self._index_name = index_name or os.environ.get("OPENSEARCH_INDEX_NAME", "messages")
        self._client = None

        if self._endpoint:
            self._client = self._create_client()

    def _create_client(self):
        """Create an OpenSearch client with SigV4 auth.

        Uses AWS SigV4 request signing for OpenSearch Serverless (service
        name: 'aoss'). The opensearch-py library is optional — if not
        available in the Lambda layer, search gracefully degrades.
        """
        try:
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from requests_aws4auth import AWS4Auth
            import boto3

            credentials = boto3.Session().get_credentials()
            region = os.environ.get("AWS_REGION", "us-east-1")
            auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                "aoss",
                session_token=credentials.token,
            )

            # Strip protocol from endpoint
            host = self._endpoint.replace("https://", "").replace("http://", "")

            return OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=30,
            )
        except ImportError:
            logger.warning("opensearch-py not available, search will be disabled")
            return None

    @property
    def is_available(self) -> bool:
        """Check if OpenSearch client is properly configured."""
        return self._client is not None

    def search(
        self,
        user_id: str,
        query: str,
        *,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Full-text search filtered by user (and optionally session).

        Returns a list of hit dicts with fields: message_id, session_id,
        role, content, created_at, score.

        Uses bool/must query with:
        - term filter on userId for tenant isolation
        - match query with AUTO fuzziness for typo tolerance
        - optional term filter on sessionId for scoped search
        """
        if not self._client:
            return []

        # Build a bool/must query — all clauses must match
        must_clauses: list[dict] = [
            {"term": {"userId": user_id}},  # Tenant isolation
            {"match": {"content": {"query": query, "fuzziness": "AUTO"}}},
        ]
        if session_id:
            must_clauses.append({"term": {"sessionId": session_id}})

        search_body = {
            "query": {"bool": {"must": must_clauses}},
            "size": limit,
            "sort": [{"_score": "desc"}, {"createdAt": "desc"}],
            "_source": [
                "messageId", "sessionId", "role", "content", "createdAt",
            ],
            "highlight": {
                "fields": {"content": {"fragment_size": 150, "number_of_fragments": 1}},
            },
        }

        try:
            response = self._client.search(
                index=self._index_name,
                body=search_body,
            )
        except Exception:
            logger.exception("OpenSearch search failed")
            return []

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            highlight = hit.get("highlight", {}).get("content", [""])[0]
            results.append({
                "message_id": source.get("messageId", ""),
                "session_id": source.get("sessionId", ""),
                "role": source.get("role", ""),
                "content": source.get("content", ""),
                "created_at": source.get("createdAt", ""),
                "snippet": highlight or source.get("content", "")[:150],
                "score": hit.get("_score", 0),
            })

        return results

    def index_message(
        self,
        *,
        user_id: str,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
        created_at: str,
    ) -> None:
        """Index a single message document."""
        if not self._client:
            return

        document = {
            "userId": user_id,
            "sessionId": session_id,
            "messageId": message_id,
            "role": role,
            "content": content,
            "createdAt": created_at,
        }

        try:
            self._client.index(
                index=self._index_name,
                id=message_id,
                body=document,
            )
        except Exception:
            logger.exception("Failed to index message %s", message_id)

    def delete_message(self, message_id: str) -> None:
        """Delete a single message from the index."""
        if not self._client:
            return

        try:
            self._client.delete(
                index=self._index_name,
                id=message_id,
                ignore=[404],
            )
        except Exception:
            logger.exception("Failed to delete message %s", message_id)

    def delete_session_messages(self, user_id: str, session_id: str) -> None:
        """Delete all messages for a session from the index."""
        if not self._client:
            return

        try:
            self._client.delete_by_query(
                index=self._index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"userId": user_id}},
                                {"term": {"sessionId": session_id}},
                            ]
                        }
                    }
                },
            )
        except Exception:
            logger.exception(
                "Failed to delete session messages for %s/%s", user_id, session_id
            )

    def ensure_index(self) -> None:
        """Create the messages index if it doesn't exist."""
        if not self._client:
            return

        try:
            if not self._client.indices.exists(index=self._index_name):
                self._client.indices.create(
                    index=self._index_name,
                    body={
                        "mappings": {
                            "properties": {
                                "userId": {"type": "keyword"},
                                "sessionId": {"type": "keyword"},
                                "messageId": {"type": "keyword"},
                                "role": {"type": "keyword"},
                                "content": {"type": "text", "analyzer": "standard"},
                                "createdAt": {"type": "date"},
                            }
                        }
                    },
                )
                logger.info("Created index: %s", self._index_name)
        except Exception:
            logger.exception("Failed to create index %s", self._index_name)
