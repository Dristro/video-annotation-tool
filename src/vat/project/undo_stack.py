from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Command:
    """A reversible mutation. `undo`/`redo` are no-argument closures over
    state already captured by the caller (e.g. the cut being restored) --
    the stack itself doesn't need to know anything about what kind of
    operation this was, only how to reverse/replay it.
    """

    undo: Callable[[], None]
    redo: Callable[[], None]


class UndoStack:
    """Small command-pattern undo/redo stack (MainWindow owns the one
    instance for the whole session). Pushing a new command clears the redo
    stack -- standard undo/redo semantics: redoing after a divergent new
    action doesn't mean anything.
    """

    def __init__(self) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        # Called after every undo()/redo() that actually ran a command.
        # MainWindow uses it to resync views that a command may have
        # changed underneath them (label set, score definitions) without
        # every individual command having to know about widgets --
        # commands stay pure Project mutations, which is what lets the
        # settings dialogs push them without holding on to MainWindow.
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def push(self, command: Command) -> None:
        self._undo.append(command)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> None:
        if not self._undo:
            return
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        self._notify()

    def redo(self) -> None:
        if not self._redo:
            return
        command = self._redo.pop()
        command.redo()
        self._undo.append(command)
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
