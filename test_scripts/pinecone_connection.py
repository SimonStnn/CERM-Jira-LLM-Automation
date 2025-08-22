# pyright: reportUnknownMemberType=false
import logging
import os
import sys
from typing import Any, cast

from pinecone import Pinecone

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from embeddings_model import client as embedding_client

from src.config import settings

log = logging.getLogger(settings.log.name)

pc = Pinecone(api_key=settings.pinecone.api_key)

index_info = cast(Any, pc.describe_index(name=settings.pinecone.index_name))
idx = pc.Index(host=cast(str, index_info.host))

query = ["How do I configure invoice numbers in CERM?"]
query_embedding = (
    embedding_client.embeddings.create(
        model=settings.azure.embedding.deployment_name, input=query
    )
    .data[0]
    .embedding
)


results = cast(
    Any,
    idx.query(
        vector=query_embedding,
        top_k=10,
        namespace=settings.pinecone.namespace,
        include_metadata=True,
        # filter={"metadata_key": { "$eq": "value1" }}
    ),
)

for match in results["matches"]:
    log.info(f"Score: {match['score']:.4f}")
    log.info(f"Source: {match['metadata'].get('source')}")
    log.info(f"Text: {match['metadata'].get('text')}\n")

else:
    log.info(f"Found {len(results['matches'])} matches")
