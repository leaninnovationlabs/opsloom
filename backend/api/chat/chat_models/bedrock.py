import os
import json
import boto3
import asyncio
from typing import List, AsyncIterator, Iterator, Optional

from backend.api.chat.chat_model_base import BaseChatModel
from backend.api.chat.models import OpsLoomMessageChunk


class BedrockChatModel(BaseChatModel):
    """Chat model for Amazon Bedrock using Anthropic Claude models."""

    def __init__(
        self,
        model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        region_name: Optional[str] = None,
        temperature: float = 0.7,
        embed_model: str = "amazon.titan-embed-text-v2:0",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.embed_model = embed_model
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)

    def _format_messages(self, messages: List[str]) -> List[dict]:
        return [{"role": "user", "content": m} for m in messages]

    def embed_query(self, query: str) -> List[float]:
        response = self.client.invoke_model(
            modelId=self.embed_model,
            contentType="application/json",
            body=json.dumps({"inputText": query}).encode("utf-8"),
        )
        result = json.loads(response["body"].read())
        return result.get("embedding", [])

    def invoke(self, messages: List[str]) -> OpsLoomMessageChunk:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": self._format_messages(messages),
            "max_tokens": 1024,
            "temperature": self.temperature,
        }
        response = self.client.invoke_model(
            modelId=self.model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        result = json.loads(response["body"].read())
        text = ""
        if result.get("content"):
            piece = result["content"][0]
            if piece.get("type") == "text":
                text = piece.get("text", "")
        return OpsLoomMessageChunk(
            content=text,
            type="text",
            id=result.get("id", ""),
            response_metadata=result,
        )

    def stream(self, messages: List[str]) -> Iterator[OpsLoomMessageChunk]:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": self._format_messages(messages),
            "max_tokens": 1024,
            "temperature": self.temperature,
            "stream": True,
        }
        response = self.client.invoke_model_with_response_stream(
            modelId=self.model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        for event in response["body"]:
            if "chunk" not in event:
                continue
            data = json.loads(event["chunk"]["bytes"].decode())
            delta = data.get("delta", {})
            text = delta.get("text", "")
            if text:
                yield OpsLoomMessageChunk(content=text, type="text", id=data.get("id", ""))

    async def ainvoke(self, messages: List[str]) -> OpsLoomMessageChunk:
        return await asyncio.to_thread(self.invoke, messages)

    async def astream(self, messages: List[str]) -> AsyncIterator[OpsLoomMessageChunk]:
        for chunk in self.stream(messages):
            yield chunk
