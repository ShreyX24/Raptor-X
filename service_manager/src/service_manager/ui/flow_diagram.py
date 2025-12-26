"""
Flow Diagram Widget - Live service communication visualization with animated connections
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QRectF, QPointF, Slot, QTimer, QLineF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient


@dataclass
class ServiceNode:
    """Represents a service node in the flow diagram"""
    name: str
    display_name: str
    x: float  # Relative position (0-1)
    y: float  # Relative position (0-1)
    status: str = "stopped"
    width: int = 100
    height: int = 40


@dataclass
class Connection:
    """Represents a connection between two services"""
    from_service: str
    to_service: str
    label: str = ""
    # Animation state
    active: bool = False
    pulse_position: float = 0.0  # 0.0 to 1.0 for animation


class FlowDiagramWidget(QWidget):
    """Live service flow visualization with animated dotted connections"""

    # Status colors
    COLORS = {
        "running": "#4ec9b0",
        "connected": "#4ec9b0",
        "starting": "#dcdcaa",
        "stopping": "#dcdcaa",
        "stopped": "#606060",
        "unreachable": "#f48771",
        "unknown": "#606060",
    }

    # Connection colors
    LINE_INACTIVE = "#404040"
    LINE_ACTIVE = "#00d4ff"  # Cyan for active communication
    PULSE_COLOR = "#ff9500"  # Orange pulse

    # Node dimensions
    NODE_WIDTH = 100
    NODE_HEIGHT = 40
    NODE_RADIUS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 280)

        # Define service nodes - cleaner horizontal flow layout
        self._nodes: Dict[str, ServiceNode] = {
            # Left column - Gemma stack (frontends below backends)
            "gemma-backend": ServiceNode("gemma-backend", "Gemma Backend", 0.02, 0.05),
            "gemma-frontend": ServiceNode("gemma-frontend", "Gemma Frontend", 0.02, 0.30),
            # Middle column - Preset Manager stack
            "preset-manager": ServiceNode("preset-manager", "Preset Manager", 0.35, 0.05),
            "pm-frontend": ServiceNode("pm-frontend", "PM Frontend", 0.35, 0.30),
            "sut-discovery": ServiceNode("sut-discovery", "SUT Discovery", 0.35, 0.55),
            # Right column - Queue Service (aligned with backends row)
            "queue-service": ServiceNode("queue-service", "Queue Service", 0.68, 0.05),
        }

        # OmniParser instances (dynamic, up to 5)
        self._omniparser_nodes: List[ServiceNode] = []
        self._update_omniparser_nodes(1)  # Default 1 instance

        # Define connections between services
        self._connections: List[Connection] = [
            Connection("gemma-frontend", "gemma-backend", ""),
            Connection("pm-frontend", "preset-manager", ""),
            Connection("gemma-backend", "preset-manager", ""),
            Connection("gemma-backend", "queue-service", ""),  # Now horizontal!
            Connection("preset-manager", "sut-discovery", ""),
        ]

        # OmniParser connections (dynamic)
        self._omniparser_connections: List[Connection] = []
        self._update_omniparser_connections()

        self.setStyleSheet("background-color: #1e1e1e;")

        # Animation timer
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_connections)
        self._animation_timer.start(50)  # 20 FPS animation

        # Track which connections are currently active (simulated by service status)
        self._active_connections: set = set()

    def _update_omniparser_nodes(self, count: int):
        """Update OmniParser instance nodes"""
        count = max(1, min(5, count))  # Clamp 1-5
        self._omniparser_nodes.clear()

        # Position OmniParser instances vertically below Queue Service
        start_y = 0.30
        spacing = 0.14

        for i in range(count):
            node = ServiceNode(
                name=f"omniparser-{i}",
                display_name=f"OmniParser {i+1}",
                x=0.68,
                y=start_y + (i * spacing),
                status="unknown"
            )
            self._omniparser_nodes.append(node)

    def _update_omniparser_connections(self):
        """Update connections to OmniParser instances"""
        self._omniparser_connections.clear()
        for node in self._omniparser_nodes:
            self._omniparser_connections.append(
                Connection("queue-service", node.name, "")
            )

    def set_omniparser_count(self, count: int):
        """Set the number of OmniParser instances to display"""
        self._update_omniparser_nodes(count)
        self._update_omniparser_connections()
        self.update()

    def set_omniparser_instances(self, instances: List[Dict]):
        """Set OmniParser instances from settings"""
        count = len(instances) if instances else 1
        count = max(1, min(5, count))
        self._update_omniparser_nodes(count)

        # Update names and status
        for i, inst in enumerate(instances[:5]):
            if i < len(self._omniparser_nodes):
                name = inst.get("name", f"OmniParser {i+1}")
                # Truncate long names
                if len(name) > 12:
                    name = name[:10] + ".."
                self._omniparser_nodes[i].display_name = name
                self._omniparser_nodes[i].status = "connected" if inst.get("enabled", True) else "stopped"

        self._update_omniparser_connections()
        self.update()

    def update_status(self, service_name: str, status: str):
        """Update the status of a service node"""
        if service_name in self._nodes:
            self._nodes[service_name].status = status
            self._update_active_connections()
            self.update()

    def update_all_statuses(self, statuses: Dict[str, str]):
        """Update all service statuses at once"""
        for name, status in statuses.items():
            if name in self._nodes:
                self._nodes[name].status = status
        self._update_active_connections()
        self.update()

    def _update_active_connections(self):
        """Update which connections should be animated based on service status"""
        self._active_connections.clear()

        # A connection is active if both endpoints are running
        all_connections = self._connections + self._omniparser_connections

        for i, conn in enumerate(all_connections):
            from_node = self._nodes.get(conn.from_service)
            to_node = self._nodes.get(conn.to_service)

            # Check OmniParser nodes too
            if not to_node:
                for op_node in self._omniparser_nodes:
                    if op_node.name == conn.to_service:
                        to_node = op_node
                        break

            if from_node and to_node:
                from_running = from_node.status in ("running", "connected")
                to_running = to_node.status in ("running", "connected")
                if from_running and to_running:
                    self._active_connections.add(i)
                    conn.active = True
                else:
                    conn.active = False

    def _animate_connections(self):
        """Animate active connections"""
        all_connections = self._connections + self._omniparser_connections

        needs_update = False
        for i, conn in enumerate(all_connections):
            if conn.active:
                conn.pulse_position += 0.03
                if conn.pulse_position > 1.0:
                    conn.pulse_position = 0.0
                needs_update = True

        if needs_update:
            self.update()

    def paintEvent(self, event):
        """Custom paint for flow diagram"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 15

        # Draw connections first (behind nodes)
        self._draw_connections(painter, width, height, margin)

        # Draw service nodes
        self._draw_nodes(painter, width, height, margin)

        # Draw OmniParser nodes
        self._draw_omniparser_nodes(painter, width, height, margin)

        # Draw legend
        self._draw_legend(painter, width, height)

        painter.end()

    def _get_node_rect(self, node: ServiceNode, width: int, height: int, margin: int) -> QRectF:
        """Calculate the rectangle for a node"""
        x = margin + node.x * (width - 2 * margin - self.NODE_WIDTH)
        y = margin + node.y * (height - 2 * margin - self.NODE_HEIGHT)
        return QRectF(x, y, self.NODE_WIDTH, self.NODE_HEIGHT)

    def _draw_nodes(self, painter: QPainter, width: int, height: int, margin: int):
        """Draw all service nodes"""
        for node in self._nodes.values():
            self._draw_single_node(painter, node, width, height, margin)

    def _draw_omniparser_nodes(self, painter: QPainter, width: int, height: int, margin: int):
        """Draw OmniParser instance nodes"""
        for node in self._omniparser_nodes:
            self._draw_single_node(painter, node, width, height, margin, is_external=True)

    def _draw_single_node(self, painter: QPainter, node: ServiceNode, width: int, height: int,
                          margin: int, is_external: bool = False):
        """Draw a single node"""
        rect = self._get_node_rect(node, width, height, margin)
        color = QColor(self.COLORS.get(node.status, self.COLORS["unknown"]))

        # Draw node background
        if is_external:
            # Dashed border for external services
            pen = QPen(color, 2, Qt.DashLine)
        else:
            pen = QPen(color, 2)

        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("#252525")))
        painter.drawRoundedRect(rect, self.NODE_RADIUS, self.NODE_RADIUS)

        # Draw status indicator dot
        dot_radius = 5
        dot_x = rect.right() - 10
        dot_y = rect.top() + 10
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(dot_x, dot_y), dot_radius, dot_radius)

        # Draw node text
        painter.setPen(QPen(QColor("#e0e0e0")))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)

        text_rect = rect.adjusted(4, 4, -4, -4)
        painter.drawText(text_rect, Qt.AlignCenter, node.display_name)

    def _draw_connections(self, painter: QPainter, width: int, height: int, margin: int):
        """Draw all connections with dotted lines and animation"""
        all_connections = self._connections + self._omniparser_connections

        for conn in all_connections:
            from_node = self._nodes.get(conn.from_service)
            to_node = self._nodes.get(conn.to_service)

            # Check OmniParser nodes
            if not to_node:
                for op_node in self._omniparser_nodes:
                    if op_node.name == conn.to_service:
                        to_node = op_node
                        break

            if not from_node or not to_node:
                continue

            from_rect = self._get_node_rect(from_node, width, height, margin)
            to_rect = self._get_node_rect(to_node, width, height, margin)

            # Calculate connection points
            start, end = self._calculate_connection_points(from_rect, to_rect)

            # Draw the connection
            self._draw_dotted_connection(painter, start, end, conn)

    def _calculate_connection_points(self, from_rect: QRectF, to_rect: QRectF) -> Tuple[QPointF, QPointF]:
        """Calculate optimal connection points between two rectangles"""
        from_center = from_rect.center()
        to_center = to_rect.center()

        # Determine which edges to connect based on relative positions
        dx = to_center.x() - from_center.x()
        dy = to_center.y() - from_center.y()

        if abs(dx) > abs(dy):
            # Horizontal connection
            if dx > 0:
                start = QPointF(from_rect.right(), from_rect.center().y())
                end = QPointF(to_rect.left(), to_rect.center().y())
            else:
                start = QPointF(from_rect.left(), from_rect.center().y())
                end = QPointF(to_rect.right(), to_rect.center().y())
        else:
            # Vertical connection
            if dy > 0:
                start = QPointF(from_rect.center().x(), from_rect.bottom())
                end = QPointF(to_rect.center().x(), to_rect.top())
            else:
                start = QPointF(from_rect.center().x(), from_rect.top())
                end = QPointF(to_rect.center().x(), to_rect.bottom())

        return start, end

    def _draw_dotted_connection(self, painter: QPainter, start: QPointF, end: QPointF, conn: Connection):
        """Draw a dotted connection line with optional animation"""
        # Base dotted line
        if conn.active:
            base_color = QColor(self.LINE_ACTIVE)
            base_color.setAlpha(100)
        else:
            base_color = QColor(self.LINE_INACTIVE)

        pen = QPen(base_color, 2, Qt.DotLine)
        pen.setDashPattern([2, 4])
        painter.setPen(pen)
        painter.drawLine(start, end)

        # Draw animated pulse if active
        if conn.active:
            self._draw_pulse(painter, start, end, conn.pulse_position)

    def _draw_pulse(self, painter: QPainter, start: QPointF, end: QPointF, position: float):
        """Draw animated pulse traveling along the connection"""
        # Calculate pulse position along the line
        pulse_x = start.x() + (end.x() - start.x()) * position
        pulse_y = start.y() + (end.y() - start.y()) * position

        # Draw glowing pulse
        pulse_center = QPointF(pulse_x, pulse_y)

        # Outer glow
        gradient = QLinearGradient(pulse_center.x() - 8, pulse_center.y(),
                                   pulse_center.x() + 8, pulse_center.y())
        gradient.setColorAt(0, QColor(0, 212, 255, 0))
        gradient.setColorAt(0.5, QColor(0, 212, 255, 200))
        gradient.setColorAt(1, QColor(0, 212, 255, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 212, 255, 150)))
        painter.drawEllipse(pulse_center, 6, 6)

        # Inner bright core
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.drawEllipse(pulse_center, 3, 3)

    def _draw_legend(self, painter: QPainter, width: int, height: int):
        """Draw status legend"""
        legend_items = [
            ("Running", "#4ec9b0"),
            ("Starting", "#dcdcaa"),
            ("Stopped", "#606060"),
            ("Error", "#f48771"),
        ]

        x = 10
        y = height - 20
        dot_radius = 4
        spacing = 70

        font = QFont("Segoe UI", 7)
        painter.setFont(font)

        for label, color in legend_items:
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x + dot_radius, y), dot_radius, dot_radius)

            painter.setPen(QPen(QColor("#707070")))
            painter.drawText(x + 12, y + 4, label)

            x += spacing


class FlowDiagramContainer(QFrame):
    """Container for flow diagram with title"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title = QLabel("Service Communication Flow")
        title.setStyleSheet("font-weight: bold; color: #cccccc; border: none;")
        layout.addWidget(title)

        self.flow_diagram = FlowDiagramWidget()
        layout.addWidget(self.flow_diagram, 1)

    @Slot(str, str)
    def update_status(self, service_name: str, status: str):
        """Update service status in the flow diagram"""
        self.flow_diagram.update_status(service_name, status)

    def update_all_statuses(self, statuses: Dict[str, str]):
        """Update all service statuses"""
        self.flow_diagram.update_all_statuses(statuses)

    def set_omniparser_instances(self, instances: List[Dict]):
        """Set OmniParser instances from settings"""
        self.flow_diagram.set_omniparser_instances(instances)
