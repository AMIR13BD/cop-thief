"""Agent decisions: LLM delegation, action sanitisation, and heuristic fallback."""

from _helpers import build_engine
from cop_thief.agents.cop_agent import build_cop_agent
from cop_thief.agents.thief_agent import build_thief_agent
from cop_thief.game.actions import Action, ActionType, Role
from cop_thief.game.board import Position
from cop_thief.game.observation import build_observation
from cop_thief.game.setup import GameParams

PARAMS = GameParams(5, 5, 25, 6, 5, True, 2, True)


def _cop_obs() -> dict:
    eng = build_engine(cop=(2, 2), thief=(2, 3), to_move=Role.COP)
    return build_observation(eng.state, Role.COP, vision_radius=2)


class _FakeLLM:
    """Returns a fixed (message, action) or raises, to drive the LLM branch."""

    def __init__(self, action=None, boom=False):
        self.action = action
        self.boom = boom

    def decide(self, role, observation, inbox):
        if self.boom:
            raise RuntimeError("llm exploded")
        return "fixed message", self.action


def test_legal_llm_action_is_used_verbatim():
    action = Action(ActionType.MOVE, Position(2, 3))
    agent = build_cop_agent(PARAMS, llm=_FakeLLM(action))
    message, chosen = agent.decide(_cop_obs(), [])
    assert message == "fixed message"
    assert chosen == action


def test_illegal_llm_move_is_sanitised_to_a_legal_one():
    agent = build_cop_agent(PARAMS, llm=_FakeLLM(Action(ActionType.MOVE, Position(9, 9))))
    _, chosen = agent.decide(_cop_obs(), [])
    assert chosen.type is ActionType.MOVE
    obs = _cop_obs()
    assert chosen.to.to_list() in [list(c) for c in _legal(obs)]


def test_valid_cop_barrier_on_own_cell_is_accepted():
    action = Action(ActionType.BARRIER, Position(2, 2))  # cop's own cell
    agent = build_cop_agent(PARAMS, llm=_FakeLLM(action))
    _, chosen = agent.decide(_cop_obs(), [])
    assert chosen == action


def test_llm_failure_falls_back_to_heuristic():
    agent = build_thief_agent(PARAMS, llm=_FakeLLM(boom=True))
    eng = build_engine(cop=(0, 0), thief=(4, 4))
    obs = build_observation(eng.state, Role.THIEF, vision_radius=2)
    message, chosen = agent.decide(obs, [])
    assert chosen.type is ActionType.MOVE
    assert isinstance(message, str) and message


def _legal(obs):
    from cop_thief.agents.strategies import legal_targets

    return legal_targets(obs, True)
