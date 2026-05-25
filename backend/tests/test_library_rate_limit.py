import pytest

from app.library.rate_limit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


@pytest.mark.asyncio
async def test_rate_limiter_waits_for_minimum_interval() -> None:
    clock = FakeClock()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    limiter = RateLimiter(
        clock=clock,
        sleeper=fake_sleep,
        intervals={"query": 3.0, "global": 0.5},
    )

    wait1 = await limiter.acquire("query")
    clock.advance(1.0)
    wait2 = await limiter.acquire("query")

    assert wait1 == 0.0
    assert wait2 == pytest.approx(2.0)
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_rate_limiter_per_key_independent() -> None:
    clock = FakeClock()

    async def fake_sleep(seconds: float) -> None:
        clock.advance(seconds)

    limiter = RateLimiter(
        clock=clock,
        sleeper=fake_sleep,
        intervals={"query": 3.0, "page": 1.0},
    )

    await limiter.acquire("query")
    page_wait = await limiter.acquire("page")
    assert page_wait == 0.0


@pytest.mark.asyncio
async def test_rate_limiter_reset_clears_history() -> None:
    clock = FakeClock()

    async def fake_sleep(seconds: float) -> None:
        clock.advance(seconds)

    limiter = RateLimiter(clock=clock, sleeper=fake_sleep, intervals={"query": 2.0})
    await limiter.acquire("query")
    limiter.reset("query")
    second_wait = await limiter.acquire("query")
    assert second_wait == 0.0
