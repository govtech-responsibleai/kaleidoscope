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
        "run_manual_migrations",
        lambda engine: calls.append("run_manual_migrations"),
    )
    monkeypatch.setattr(
        main_module,
        "setup_phoenix_instrumentation",
        lambda project_name: None,
    )
    monkeypatch.setattr(main_module.engine, "dispose", lambda: calls.append("dispose"))
    monkeypatch.setattr(extensions_module, "load_extensions", lambda: calls.append("load_extensions"))

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(main_module.lifespan(main_module.app))

    assert calls == [
        "init_db",
        "run_manual_migrations",
        "load_extensions",
        "dispose",
    ]
