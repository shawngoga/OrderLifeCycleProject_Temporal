import pytest
import asyncio
from temporalio.client import Client

@pytest.mark.asyncio
async def test_temporal_connection():
    try:
        client = await Client.connect("localhost:7233")
        assert client is not None
    except Exception as e:
        pytest.fail(f"Temporal connection failed: {e}")

