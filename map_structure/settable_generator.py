from functools import wraps, partial
from types import TracebackType
from typing import TypeVar, Generator, Type, Optional, Any, overload, Callable, \
    Generic

_T_co = TypeVar('_T_co', covariant=True)
_V_co = TypeVar('_V_co', covariant=True)
_T_cntr = TypeVar('_T_cntr', contravariant=True)


class SettableGenerator(Generator[_T_co, _T_cntr, _V_co]):
    generator: Generator[_T_co, _T_cntr, _V_co]
    _result: Optional[_V_co]
    _send_value: Optional[_T_cntr]
    _is_set: bool
    _exhausted: bool

    def __init__(self, generator: Generator[_T_co, _T_cntr, _V_co],
                 default: _T_cntr = None):
        self.generator = generator
        self.default = default
        self._result = None
        self._send_value = None
        self._is_set = False
        self._exhausted = False

    def set(self, value: _T_cntr):
        self.guard_is_set()
        self._send_value = value
        self._is_set = True

    def __next__(self) -> _T_co:
        send_value = self._send_value
        self._is_set = False
        self._send_value = self.default
        return self.forward(send_value)

    def send(self, send_value: _T_cntr) -> _T_co:
        self.guard_is_set()
        return self.forward(send_value)

    def guard_is_set(self):
        if self._is_set:
            raise RuntimeError(
                'Generator has already been set to {}'.format(self._send_value))

    def forward(self, send_value: _T_cntr) -> _T_co:
        try:
            return self.generator.send(send_value)
        except StopIteration as e:
            self._exhausted = True
            self._result = e.value
            raise e

    @property
    def result(self) -> _V_co:
        if not self._exhausted:
            raise RuntimeError(
                'Result not available for incomplete generators')
        return self._result

    def throw(self, typ: Type[BaseException],
              val: Optional[BaseException] = None,
              tb: Optional[TracebackType] = None) -> _T_co:
        return self.generator.throw(typ, val, tb)

    def map(self, generator: Generator[_T_co, Any, Any]) -> _V_co:
        for x in generator:
            self.set(x)

        return self.result


GeneratorFactory = Callable[..., Generator[_T_co, _T_cntr, _V_co]]


class SettableGeneratorFactory(Generic[_T_co, _T_cntr, _V_co]):
    generator_factory: GeneratorFactory[_T_co, _T_cntr, _V_co]
    default: _T_cntr
    _latest: SettableGenerator[_T_co, _T_cntr, _V_co]

    def __init__(
            self,
            generator_factory: GeneratorFactory[_T_co, _T_cntr, _V_co],
            default: _T_cntr = None,
    ):
        self.generator_factory = generator_factory
        self.default = default

    def __call__(self, *args, **kwargs) \
            -> SettableGenerator[_T_co, _T_cntr, _V_co]:
        self._latest = SettableGenerator(
            self.generator_factory(*args, **kwargs),
            default=self.default,
        )
        return self._latest

    def map(self, generator: Generator[_T_co, Any, Any]) -> _V_co:
        for x in generator:
            self._latest.set(x)

        return self._latest.result


@overload
def settable(
        *,
        default: _T_cntr = None,
) -> Callable[
           [GeneratorFactory[_T_co, _T_cntr, _V_co]],
           SettableGeneratorFactory[_T_co, _T_cntr, _V_co],
        ]: ...


@overload
def settable(
        generator: GeneratorFactory[_T_co, _T_cntr, _V_co],
        *,
        default: _T_cntr = None,
) -> SettableGeneratorFactory[_T_co, _T_cntr, _V_co]: ...


def settable(
        generator: GeneratorFactory[_T_co, _T_cntr, _V_co] = None,
        *,
        default: _T_cntr = None,
):
    if generator is None:
        return partial(settable, default=default)

    inner = wraps(generator)(
        SettableGeneratorFactory(generator, default=default)
    )

    return inner
