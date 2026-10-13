from typing import Protocol, Any
from dataclasses import dataclass, field


class Unavailable(RuntimeError):
    pass


class InfrastructureError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class Stopped(RuntimeError):
    pass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    cost_kind: str = "actual"
    inference_seconds: float = 0.0
    calls: list = field(default_factory=list)


class CheckoutAdapter(Protocol):
    async def run(self, page: Any, task: dict, controls: Any) -> Usage: ...


@dataclass
class Ledger:
    cap: float | None = None
    spent: float = 0.0
    reserved: float = 0.0

    def reserve(self, amount: float):
        if (
            self.cap is not None
            and self.spent + self.reserved + amount > self.cap + 1e-10
        ):
            raise BudgetExceeded(
                "Spending cap cannot cover the next bounded inference request."
            )
        self.reserved += amount

    def settle(self, reserved: float, actual: float):
        self.reserved = max(0, self.reserved - reserved)
        self.spent += actual
