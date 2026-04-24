from contextlib import AsyncExitStack

import pytest

import src.main as main_module
import src.extensions as extensions_module


@pytest.mark.asyncio
async def test_lifespan_does_not_run_runtime_rubric_bootstrap(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(main_module, "init_db", lambda: calls.append("init_db"))
    monkeypatch.setattr(
        main_module,
        "setup_langfuse_instrumentation",
        lambda: calls.append("setup_langfuse_instrumentation"),
    )
    monkeypatch.setattr(
        main_module.engine,
        "dispose",
        lambda: calls.append("dispose"),
    )
    monkeypatch.setattr(extensions_module, "load_extensions", lambda: calls.append("load_extensions"))

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(main_module.lifespan(main_module.app))

    assert calls == [
        "init_db",
        "load_extensions",
        "setup_langfuse_instrumentation",
        "dispose",
    ]
