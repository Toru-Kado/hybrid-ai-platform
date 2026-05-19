"""DynamoDB Streams event handler for indexing messages into OpenSearch.

Processes INSERT/MODIFY events to index messages, and REMOVE events
to delete them from the search index. Only processes MESSAGE entity
types (ignores SESSION records).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.lambda_handlers.search_client import OpenSearchClient

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy-initialized client
_search_client: OpenSearchClient | None = None


def _get_search_client() -> OpenSearchClient:
    global _search_client
    if _search_client is None:
        _search_client = OpenSearchClient()
        _search_client.ensure_index()
    return _search_client


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process DynamoDB Streams events and sync to OpenSearch.

    Event records contain:
        - eventName: INSERT | MODIFY | REMOVE
        - dynamodb.NewImage: the new item (for INSERT/MODIFY)
        - dynamodb.OldImage: the old item (for MODIFY/REMOVE)
        - dynamodb.Keys: the key attributes
    """
    client = _get_search_client()
    if not client.is_available:
        logger.warning("OpenSearch client not available, skipping indexing")
        return {"statusCode": 200, "body": "OpenSearch not configured"}

    records = event.get("Records", [])
    processed = 0
    errors = 0

    for record in records:
        try:
            _process_record(client, record)
            processed += 1
        except Exception:
            logger.exception("Failed to process record")
            errors += 1

    logger.info(
        "Processed %d records (%d errors) from %d total",
        processed,
        errors,
        len(records),
    )

    return {
        "statusCode": 200,
        "body": f"Processed {processed} records, {errors} errors",
    }


def _process_record(client: OpenSearchClient, record: dict[str, Any]) -> None:
    """Process a single DynamoDB Stream record."""
    event_name = record.get("eventName", "")
    dynamodb_record = record.get("dynamodb", {})

    if event_name in ("INSERT", "MODIFY"):
        new_image = dynamodb_record.get("NewImage", {})
        _handle_upsert(client, new_image)
    elif event_name == "REMOVE":
        old_image = dynamodb_record.get("OldImage", {})
        _handle_delete(client, old_image)


def _handle_upsert(client: OpenSearchClient, image: dict[str, Any]) -> None:
    """Index a new or modified message."""
    entity_type = _get_string(image, "entity_type")
    if entity_type != "MESSAGE":
        return

    # Extract fields from DynamoDB record format
    user_id = _extract_user_id_from_pk(image)
    if not user_id:
        return

    message_id = _get_string(image, "message_id")
    session_id = _get_string(image, "session_id")
    role = _get_string(image, "role")
    content = _get_string(image, "content")
    created_at = _get_string(image, "created_at")

    if not all([message_id, session_id, role, content]):
        logger.warning("Incomplete message record, skipping")
        return

    client.index_message(
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        role=role,
        content=content,
        created_at=created_at,
    )


def _handle_delete(client: OpenSearchClient, image: dict[str, Any]) -> None:
    """Remove a deleted message from the index."""
    entity_type = _get_string(image, "entity_type")
    if entity_type != "MESSAGE":
        return

    message_id = _get_string(image, "message_id")
    if message_id:
        client.delete_message(message_id)


def _extract_user_id_from_pk(image: dict[str, Any]) -> str | None:
    """Extract user_id from the PK attribute (USER#{userId})."""
    pk = _get_string(image, "PK")
    if pk and pk.startswith("USER#"):
        return pk[5:]
    return None


def _get_string(image: dict[str, Any], key: str) -> str:
    """Extract a string value from a DynamoDB Streams image.

    DynamoDB Streams format uses type descriptors: {"S": "value"}, {"N": "123"}, etc.
    """
    value = image.get(key, {})
    if isinstance(value, dict):
        return value.get("S", "") or value.get("N", "")
    if isinstance(value, str):
        return value
    return ""
