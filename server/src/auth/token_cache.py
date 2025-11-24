"""
In-memory token cache for fast user_id lookup by token hash.
Maps token_hash -> (user_id, capability, expires_at) for O(1) lookups.
"""

import hashlib
import threading
import time
from typing import Optional

from src.dao.token_repo import TokenRepo


class TokenCache:
    def __init__(self):
        self._cache: dict[str, tuple[str, str, int]] = {}  # {token_hash: (user_id, capability, expires_at)}
        self._lock = threading.RLock()
    
    def load_from_db(self, token_repo: TokenRepo) -> None:
        with self._lock:
            self._cache.clear()
            tokens = token_repo.list_all_active_tokens()
            for token in tokens:
                # Store mapping: token_hash -> (user_id, capability, expires_at)
                self._cache[token.token_hash] = (token.user_id, token.capability, token.expires_at)
    
    def get(self, token_plaintext: str) -> Optional[tuple[str, str]]:
        token_hash = self._hash_token(token_plaintext)
        with self._lock:
            entry = self._cache.get(token_hash)
            if entry is None:
                return None
            
            user_id, capability, expires_at = entry
            
            # Check if token has expired
            if int(time.time()) >= expires_at:
                # Token expired, remove from cache
                self._cache.pop(token_hash, None)
                return None
            
            return (user_id, capability)
    
    def add(self, token_plaintext: str, user_id: str, capability: str, expires_at: int) -> None:
        token_hash = self._hash_token(token_plaintext)
        with self._lock:
            self._cache[token_hash] = (user_id, capability, expires_at)
    
    def remove_by_hash(self, token_hash: str) -> None:
        with self._lock:
            self._cache.pop(token_hash, None)
    
    def invalidate_user_tokens(self, user_id: str) -> None:
        with self._lock:
            self._cache = {
                hash_key: (uid, cap, exp) 
                for hash_key, (uid, cap, exp) in self._cache.items() 
                if uid != user_id
            }
    
    def size(self) -> int:
        with self._lock:
            return len(self._cache)
    
    @staticmethod
    def _hash_token(token_plaintext: str) -> str:
        return hashlib.sha256(token_plaintext.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_token_for_storage(token_plaintext: str) -> str:
        return TokenCache._hash_token(token_plaintext)
