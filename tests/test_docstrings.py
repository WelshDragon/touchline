"""Docstring completeness checks for parameters and return values."""

from __future__ import annotations

import inspect
import pkgutil
from types import ModuleType
from typing import Iterable, List, Set

import pytest
from numpydoc.docscrape import NumpyDocString

import touchline


def _collect_modules(root: ModuleType) -> List[ModuleType]:
    modules: List[ModuleType] = []
    seen: Set[str] = set()
    stack: List[ModuleType] = [root]

    while stack:
        module = stack.pop()
        name = getattr(module, "__name__", None)
        if name is None or name in seen:
            continue
        seen.add(name)
        modules.append(module)

        module_path = getattr(module, "__path__", None)
        if module_path is None:
            continue

        for finder in pkgutil.walk_packages(module_path, prefix=f"{name}."):
            try:
                submodule = __import__(finder.name, fromlist=["*"])
            except Exception:
                continue
            stack.append(submodule)

    return modules


def _collect_public_callables(modules: Iterable[ModuleType]) -> List[object]:
    items: List[object] = []
    seen: Set[int] = set()

    def add(obj: object) -> None:
        obj_id = id(obj)
        if obj_id not in seen:
            seen.add(obj_id)
            items.append(obj)

    for module in modules:
        include_private = True
        add(module)
        for name, obj in inspect.getmembers(module):
            if name.startswith("__"):
                continue
            if not include_private and name.startswith("_"):
                continue
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                add(obj)
            elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                add(obj)
                class_private = include_private
                for meth_name, meth in inspect.getmembers(obj):
                    if meth_name.startswith("__"):
                        continue
                    if not class_private and meth_name.startswith("_"):
                        continue
                    if inspect.isfunction(meth):
                        if meth.__module__ == obj.__module__:
                            add(meth)
                    elif inspect.ismethod(meth):
                        func = meth.__func__
                        if func.__module__ == obj.__module__:
                            add(func)

    return items


def _documented_parameters(docstring: str | None) -> Set[str]:
    if not docstring:
        return set()
    parsed = NumpyDocString(docstring)
    return {name for name, _, _ in parsed["Parameters"]}


def _has_returns_section(docstring: str | None) -> bool:
    if not docstring:
        return False
    parsed = NumpyDocString(docstring)
    return bool(parsed["Returns"])


def _needs_returns_documentation(sig: inspect.Signature) -> bool:
    annotation = sig.return_annotation
    if annotation is inspect.Signature.empty:
        return False
    if annotation in {None, type(None)}:
        return False
    if isinstance(annotation, str):
        normalized = annotation.strip().lower()
        if normalized in {"none", "nonetype", "typing.none", "builtins.none", "builtins.nonetype"}:
            return False
    return True


_MODULES = _collect_modules(touchline)
_PUBLIC_OBJECTS = _collect_public_callables(_MODULES)


def _object_id(obj: object) -> str:
    module = getattr(obj, "__module__", "<unknown>")
    name = getattr(obj, "__qualname__", getattr(obj, "__name__", repr(obj)))
    return f"{module}.{name}"


@pytest.mark.parametrize("obj", _PUBLIC_OBJECTS, ids=_object_id)
def test_parameters_are_documented(obj: object) -> None:
    """Assert that every parameter in the signature is described in the docstring."""
    if inspect.ismodule(obj):
        pytest.skip("Modules are handled separately")

    docstring = inspect.getdoc(obj)
    signature = inspect.signature(obj)
    params_to_check = [
        p
        for p in signature.parameters.values()
        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        and p.name not in {"self", "cls"}
    ]

    if not params_to_check:
        pytest.skip("No parameters requiring documentation")

    documented = _documented_parameters(docstring)
    missing = [p.name for p in params_to_check if p.name not in documented]

    assert not missing, (
        f"Docstring for {_object_id(obj)} is missing parameter entries: "
        + ", ".join(missing)
    )


@pytest.mark.parametrize("obj", _PUBLIC_OBJECTS, ids=_object_id)
def test_returns_are_documented(obj: object) -> None:
    """Require a Returns section whenever the callable annotates a non-None value."""
    if inspect.ismodule(obj):
        pytest.skip("Modules are handled separately")

    docstring = inspect.getdoc(obj)
    signature = inspect.signature(obj)

    if not _needs_returns_documentation(signature):
        pytest.skip("Return value does not require documentation")

    assert _has_returns_section(docstring), (
        f"Docstring for {_object_id(obj)} is missing a Returns section"
    )