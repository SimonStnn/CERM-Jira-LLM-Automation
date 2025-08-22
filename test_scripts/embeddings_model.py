import logging
import os
import sys

from openai import AzureOpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.config import settings

log = logging.getLogger(settings.log.name)

client = AzureOpenAI(
    api_key=settings.azure.api_key,
    api_version=settings.azure.api_version,
    azure_endpoint=settings.azure.embedding.endpoint,
)


if __name__ == "__main__":
    response = client.embeddings.create(
        input=["How do I configure invoice numbers in CERM?"],
        model=settings.azure.embedding.deployment_name,
    )

    for item in response.data:
        length = len(item.embedding)
        log.info(
            f"data[{item.index}]: length={length}, "
            f"[{item.embedding[0]:9f}, {item.embedding[1]:9f}, "
            f"..., {item.embedding[length-2]:9f}, {item.embedding[length-1]:9f}]"
        )
    log.info(response.usage)
