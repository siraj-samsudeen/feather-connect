"""What a server started for one scenario wrote to its log. The texts the
readiness checks write live here; the steps only ask questions."""

from support import stack


class ServerLog:
    def __init__(self, world):
        self.world = world

    def lines(self):
        process = self.world.scenario_server
        if process is None:
            raise AssertionError("the scenario started no server of its own")
        return stack.log_path(process).read_text(encoding="utf-8", errors="replace").splitlines()

    def has_line(self, text):
        """(yes?, the log): a line of the log holds that text."""
        lines = self.lines()
        return any(text in line for line in lines), "\n".join(lines[-40:])
