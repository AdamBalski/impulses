import contextlib
import threading
import collections
import logging
import os
import pathlib
import abc
import typing
import pydantic

T = typing.TypeVar("T", bound=pydantic.BaseModel)

class Type(abc.ABC, typing.Generic[T]):
    @abc.abstractmethod
    def serialize(self, value: T, filepath: pathlib.Path) -> None:
        pass
    @abc.abstractmethod
    def deserialize(self, filepath: pathlib.Path) -> T:
        pass
    @staticmethod
    def for_pydantic_model(model_cls: typing.Type[T], \
                           default: typing.Callable[[], typing.Optional[T]]=lambda: None) -> "Type[T]":
        class __Type(Type):
            def __init__(self, default: typing.Callable[[], typing.Optional[T]]):
                self.default = default
            def serialize(self, value, filepath: pathlib.Path) -> None:
                with open(filepath, "w") as file:
                    print(value)
                    file.write(value.model_dump_json())
            def deserialize(self, filepath: pathlib.Path) -> typing.Optional[T]:
                try:
                    with open(filepath, "r") as file:
                        return model_cls.model_validate_json(file.read())
                except FileNotFoundError:
                    return self.default()
        return __Type(default)

class PerStringLock:
    def __init__(self):
        self.mu = threading.Lock()
        self.locks = collections.defaultdict(threading.Lock)
        self.counter = collections.defaultdict(lambda: 0)
    def acquire(self, key: str):
        lock = None
        with self.mu:
            lock = self.locks[key]
            self.counter[key] += 1
        lock.acquire()
    def release(self, key: str):
        with self.mu:
            lock = self.locks[key]
            self.counter[key] += 1
            if self.counter[key] == 0:
                del self.locks[key]
                del self.counter[key]
            lock.release()

class AtomicCounter:
    def __init__(self):
        self.val = -1
        self.lock = threading.Lock()
    def next(self):
        with self.lock:
            self.val += 1
            return self.val

class PersistentDao:
    def __init__(self, storage_dir: pathlib.Path):
        os.makedirs(storage_dir / "tmp", exist_ok=True)
        os.makedirs(storage_dir / "persistent_obj_dir", exist_ok=True)
        self.storage_dir = storage_dir
        self.cache = {}
        self.tmp_name_counter = AtomicCounter()
        self.locks = PerStringLock()
        
    def flush(self, obj_name, value, type_obj: Type):
        logging.debug(f"Writing {type_obj} {obj_name} to data store")
        self.cache[obj_name] = value
        tmp_path = self.get_tmp_path()
        obj_path = self.get_path(obj_name)
        type_obj.serialize(value, tmp_path)
        os.replace(tmp_path, obj_path)

    @contextlib.contextmanager
    def locked_access(self, obj_name: str, type_obj: Type):
        try:
            self.locks.acquire(obj_name)
            yield self.read(obj_name, type_obj), lambda new: self.flush(obj_name, new, type_obj)
        finally:
            self.locks.release(obj_name)


    def read(self, obj_name, type_obj: Type):
        if obj_name in self.cache:
            return self.cache[obj_name]
        self.cache[obj_name] = result = type_obj.deserialize(self.get_path(obj_name))
        return result

    def get_path(self, obj_name: str) -> pathlib.Path:
        return self.storage_dir / "persistent_obj_dir" / obj_name
    def get_tmp_path(self) -> pathlib.Path:
        return self.storage_dir / "tmp" / str(self.tmp_name_counter.next())

class TypedPersistentDao(typing.Generic[T]):
    def __init__(self, dao: PersistentDao, type_obj: Type[T]):
        self.dao = dao
        self.type_obj = type_obj
    def flush(self, obj_name: str, value: T):
        return self.dao.flush(obj_name, value, self.type_obj)
    def read(self, obj_name: str) -> T:
        return self.dao.read(obj_name, self.type_obj)
    def locked_access(self, obj_name) -> typing.ContextManager[typing.Tuple[T, typing.Callable[[T], None]]]:
        return self.dao.locked_access(obj_name, self.type_obj)
