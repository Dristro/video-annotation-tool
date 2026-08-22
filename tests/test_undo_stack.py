from vat.project.undo_stack import Command, UndoStack


def _tracking_command(log, name):
    return Command(undo=lambda: log.append(f"undo-{name}"), redo=lambda: log.append(f"redo-{name}"))


def test_undo_calls_command_undo():
    log = []
    stack = UndoStack()
    stack.push(_tracking_command(log, "a"))

    stack.undo()

    assert log == ["undo-a"]


def test_redo_calls_command_redo():
    log = []
    stack = UndoStack()
    stack.push(_tracking_command(log, "a"))
    stack.undo()

    stack.redo()

    assert log == ["undo-a", "redo-a"]


def test_undo_on_empty_stack_is_a_noop():
    stack = UndoStack()
    stack.undo()  # must not raise
    assert stack.can_undo() is False


def test_redo_on_empty_stack_is_a_noop():
    stack = UndoStack()
    stack.redo()  # must not raise
    assert stack.can_redo() is False


def test_pushing_after_undo_clears_redo_stack():
    log = []
    stack = UndoStack()
    stack.push(_tracking_command(log, "a"))
    stack.undo()
    assert stack.can_redo() is True

    stack.push(_tracking_command(log, "b"))

    assert stack.can_redo() is False


def test_can_undo_can_redo_reflect_stack_state():
    stack = UndoStack()
    assert stack.can_undo() is False
    assert stack.can_redo() is False

    stack.push(_tracking_command([], "a"))
    assert stack.can_undo() is True
    assert stack.can_redo() is False

    stack.undo()
    assert stack.can_undo() is False
    assert stack.can_redo() is True


def test_multiple_undo_redo_round_trip_in_order():
    log = []
    stack = UndoStack()
    stack.push(_tracking_command(log, "a"))
    stack.push(_tracking_command(log, "b"))

    stack.undo()
    stack.undo()

    assert log == ["undo-b", "undo-a"]

    stack.redo()
    stack.redo()

    assert log == ["undo-b", "undo-a", "redo-a", "redo-b"]
