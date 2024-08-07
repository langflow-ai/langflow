"""
This code is adapted from the DVC project.

Original source:
https://github.com/iterative/dvc/blob/c5bac1c8cfdb2c0f54d52ac61ff754e6f583822a/dvc/dagascii.py

The original code has been modified to focus on drawing a Directed Acyclic Graph (DAG) in ASCII
using the `grandalf` library. Non-essential parts have been removed, and the code has been
refactored to suit this specific use case.


"""

import math

from grandalf.graphs import Edge as GrandalfEdge
from grandalf.graphs import Graph as GrandalfGraph
from grandalf.graphs import Vertex as GrandalfVertex
from grandalf.layouts import SugiyamaLayout
from grandalf.routing import EdgeViewer, route_with_lines


class VertexViewer:
    """Class to define vertex box boundaries that will be accounted for during graph building by grandalf."""

    HEIGHT = 3  # top and bottom box edges + text

    def __init__(self, name):
        self._h = self.HEIGHT  # top and bottom box edges + text
        self._w = len(name) + 2  # right and left bottom edges + text

    @property
    def h(self):
        return self._h

    @property
    def w(self):
        return self._w


class AsciiCanvas:
    """Class for drawing in ASCII."""

    def __init__(self, cols, lines):
        assert cols > 1
        assert lines > 1
        self.cols = cols
        self.lines = lines
        self.canvas = [[" "] * cols for _ in range(lines)]

    def get_lines(self):
        return map("".join, self.canvas)

    def draws(self):
        return "\n".join(self.get_lines())

    def draw(self):
        """Draws ASCII canvas on the screen."""
        lines = self.get_lines()
        print("\n".join(lines))

    def point(self, x, y, char):
        """Create a point on ASCII canvas."""
        assert len(char) == 1
        assert 0 <= x < self.cols
        assert 0 <= y < self.lines
        self.canvas[y][x] = char

    def line(self, x0, y0, x1, y1, char):
        """Create a line on ASCII canvas."""
        if x0 > x1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1

        dx = x1 - x0
        dy = y1 - y0

        if dx == 0 and dy == 0:
            self.point(x0, y0, char)
        elif abs(dx) >= abs(dy):
            for x in range(x0, x1 + 1):
                y = y0 + int(round((x - x0) * dy / float(dx))) if dx else y0
                self.point(x, y, char)
        else:
            for y in range(min(y0, y1), max(y0, y1) + 1):
                x = x0 + int(round((y - y0) * dx / float(dy))) if dy else x0
                self.point(x, y, char)

    def text(self, x, y, text):
        """Print a text on ASCII canvas."""
        for i, char in enumerate(text):
            self.point(x + i, y, char)

    def box(self, x0, y0, width, height):
        """Create a box on ASCII canvas."""
        assert width > 1
        assert height > 1
        width -= 1
        height -= 1

        for x in range(x0, x0 + width):
            self.point(x, y0, "-")
            self.point(x, y0 + height, "-")
        for y in range(y0, y0 + height):
            self.point(x0, y, "|")
            self.point(x0 + width, y, "|")
        self.point(x0, y0, "+")
        self.point(x0 + width, y0, "+")
        self.point(x0, y0 + height, "+")
        self.point(x0 + width, y0 + height, "+")


def build_sugiyama_layout(vertexes, edges):
    vertexes = {v: GrandalfVertex(v) for v in vertexes}
    edges = [GrandalfEdge(vertexes[s], vertexes[e]) for s, e in edges]
    graph = GrandalfGraph(vertexes.values(), edges)

    for vertex in vertexes.values():
        vertex.view = VertexViewer(vertex.data)

    minw = min([v.view.w for v in vertexes.values()])

    for edge in edges:
        edge.view = EdgeViewer()

    sug = SugiyamaLayout(graph.C[0])
    roots = [v for v in sug.g.sV if len(v.e_in()) == 0]
    sug.init_all(roots=roots, optimize=True)

    sug.yspace = VertexViewer.HEIGHT
    sug.xspace = minw
    sug.route_edge = route_with_lines

    sug.draw()
    return sug


def draw_graph(vertexes, edges, return_ascii=True):
    """Build a DAG and draw it in ASCII."""
    sug = build_sugiyama_layout(vertexes, edges)

    Xs = []
    Ys = []

    for vertex in sug.g.sV:
        Xs.extend([vertex.view.xy[0] - vertex.view.w / 2.0, vertex.view.xy[0] + vertex.view.w / 2.0])
        Ys.extend([vertex.view.xy[1], vertex.view.xy[1] + vertex.view.h])

    for edge in sug.g.sE:
        for x, y in edge.view._pts:
            Xs.append(x)
            Ys.append(y)

    minx = min(Xs)
    miny = min(Ys)
    maxx = max(Xs)
    maxy = max(Ys)

    canvas_cols = int(math.ceil(maxx - minx)) + 1
    canvas_lines = int(round(maxy - miny))

    canvas = AsciiCanvas(canvas_cols, canvas_lines)

    for edge in sug.g.sE:
        assert len(edge.view._pts) > 1
        for index in range(1, len(edge.view._pts)):
            start = edge.view._pts[index - 1]
            end = edge.view._pts[index]
            canvas.line(
                int(round(start[0] - minx)),
                int(round(start[1] - miny)),
                int(round(end[0] - minx)),
                int(round(end[1] - miny)),
                "*",
            )

    for vertex in sug.g.sV:
        x = vertex.view.xy[0] - vertex.view.w / 2.0
        y = vertex.view.xy[1]
        canvas.box(int(round(x - minx)), int(round(y - miny)), vertex.view.w, vertex.view.h)
        canvas.text(int(round(x - minx)) + 1, int(round(y - miny)) + 1, vertex.data)
    if return_ascii:
        return canvas.draws()
    else:
        canvas.draw()
