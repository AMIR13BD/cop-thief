"""MCP client path: the orchestrator drives a full series THROUGH both servers.

Uses FastMCP's in-memory transport (no network) so the orchestration logic — sole
referee in the client, NL relayed via the servers, technical-loss void/re-run — is
tested deterministically. A real HTTP run is exercised separately.
"""

from cop_thief.config import Config
from cop_thief.game.actions import Role
from cop_thief.mcp_servers.server_app import build_mcp_app
from cop_thief.orchestrator.mcp_series import MCPSeriesRunner


def _in_memory_factory(role: Role):
    from fastmcp import Client

    return Client(build_mcp_app(role))


def test_mcp_series_runs_full_game_in_memory():
    config = Config.load()
    runner = MCPSeriesRunner(config, llm=None, log=False, client_factory=_in_memory_factory)
    result = runner.run()

    assert len(result.sub_games) == config.game_params().num_games
    cop = sum(s.score["cop"] for s in result.sub_games)
    thief = sum(s.score["thief"] for s in result.sub_games)
    assert result.totals == {"cop": cop, "thief": thief}
    assert all(s.result in ("cop_win", "thief_win") for s in result.sub_games)


class _FlakyClient:
    """Wrap an in-memory client and fail the first ``state['fails']`` tool calls."""

    def __init__(self, inner, state: dict):
        self._inner_cm = inner
        self._state = state
        self._client = None

    async def __aenter__(self):
        self._client = await self._inner_cm.__aenter__()
        return self

    async def __aexit__(self, *exc):
        return await self._inner_cm.__aexit__(*exc)

    async def call_tool(self, name, args):
        if self._state["fails"] > 0:
            self._state["fails"] -= 1
            raise RuntimeError("simulated transport failure")
        return await self._client.call_tool(name, args)


def test_technical_loss_is_voided_and_rerun():
    config = Config.load()
    # max_retries=3 -> each tool call is attempted 4 times; 4 failures void sub-game 1.
    shared = {"fails": int(config.match.get("max_retries", 3)) + 1}

    def factory(role: Role):
        from fastmcp import Client

        return _FlakyClient(Client(build_mcp_app(role)), shared)

    runner = MCPSeriesRunner(config, llm=None, log=False, client_factory=factory)
    result = runner.run()

    # Despite the forced Technical Loss on the first attempt, the series still
    # completes the full quota of valid sub-games.
    assert len(result.sub_games) == config.game_params().num_games
    assert shared["fails"] == 0
