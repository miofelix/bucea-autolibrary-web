"""In-memory store of per-library-user sessions.

Sessions live only in the process — restarting the backend forces every
account to log in again. That's a deliberate choice: persisting cookies on
disk requires another layer of encryption and increases blast radius if
the database leaks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.library.session import LibrarySession


@dataclass
class LibrarySessionStore:
    _sessions: dict[int, LibrarySession] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, library_user_id: int) -> LibrarySession:
        async with self._lock:
            session = self._sessions.get(library_user_id)
            if session is None:
                session = LibrarySession(library_user_id=library_user_id)
                self._sessions[library_user_id] = session
            return session

    async def set(self, session: LibrarySession) -> None:
        async with self._lock:
            self._sessions[session.library_user_id] = session

    async def clear(self, library_user_id: int) -> None:
        async with self._lock:
            self._sessions.pop(library_user_id, None)


_global_store = LibrarySessionStore()


def get_library_session_store() -> LibrarySessionStore:
    return _global_store
