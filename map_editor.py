# 修正済み map_editor.py （ID管理分離対応 + 長方形描画済）
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import math

TERRITORY_COLORS = ["yellow", "red", "orange", "blue", "lightblue", "purple", "lightyellow", "magenta"]

class Node:
    def __init__(self, node_id, x, y, node_type, name, score=0):
        self.id = node_id
        self.x = x
        self.y = y
        self.type = node_type
        self.name = name
        self.score = score
        self.links = []
        self.assigned_color = None
        self.circle_id = None
        self.text_id = None

class MapEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("マップエディタ")
        self.mode = "normal"
        self.current_node_type = None
        self.nodes = {}
        self.node_counters = {"コンビニ": 0, "スーパー": 0, "ホール": 0, "陣地": 0, "中心大厦": 0}
        self.link_mode_source = None
        self.links_lines = {}
        self.drag_data = {"node": None, "x": 0, "y": 0}

        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, width=800, height=600, bg="white")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)

        self.control_panel = ttk.Frame(self.main_frame, width=300)
        self.control_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.build_control_panel()

        self.main_frame.columnconfigure(0, weight=3)
        self.main_frame.columnconfigure(1, weight=1)

    def build_control_panel(self):
        ttk.Label(self.control_panel, text="モード選択").pack(pady=5)
        btn_frame = ttk.Frame(self.control_panel)
        btn_frame.pack(pady=5, fill=tk.X)
        for node_type in ["コンビニ", "スーパー", "ホール", "中心大厦", "陣地"]:
            btn = ttk.Button(btn_frame, text=f"追加: {node_type}",
                             command=lambda nt=node_type: self.set_add_node_mode(nt))
            btn.pack(fill=tk.X, pady=2)

        self.link_btn = ttk.Button(self.control_panel, text="リンクモード OFF", command=self.toggle_link_mode)
        self.link_btn.pack(fill=tk.X, pady=5)
        ttk.Separator(self.control_panel, orient="horizontal").pack(fill=tk.X, pady=10)

        ttk.Label(self.control_panel, text="ノード編集").pack(pady=5)
        self.edit_node_id = None
        self.name_var = tk.StringVar()
        self.score_var = tk.StringVar()

        nf = ttk.Frame(self.control_panel)
        nf.pack(fill=tk.X, pady=2)
        ttk.Label(nf, text="名称:").pack(side=tk.LEFT)
        ttk.Entry(nf, textvariable=self.name_var).pack(side=tk.RIGHT, fill=tk.X, expand=True)

        sf = ttk.Frame(self.control_panel)
        sf.pack(fill=tk.X, pady=2)
        ttk.Label(sf, text="得点:").pack(side=tk.LEFT)
        ttk.Entry(sf, textvariable=self.score_var).pack(side=tk.RIGHT, fill=tk.X, expand=True)

        ttk.Button(self.control_panel, text="更新", command=self.update_node_info).pack(pady=5, fill=tk.X)
        ttk.Separator(self.control_panel, orient="horizontal").pack(fill=tk.X, pady=10)
        ttk.Button(self.control_panel, text="保存", command=self.save_map).pack(fill=tk.X, pady=2)
        ttk.Button(self.control_panel, text="読込", command=self.load_map).pack(fill=tk.X, pady=2)

    def set_add_node_mode(self, node_type):
        self.mode = "add_node"
        self.current_node_type = node_type
        self.link_mode_source = None
        self.link_btn.config(text="リンクモード OFF")
        messagebox.showinfo("モード変更", f"{node_type} ノードの追加モードになりました。\nCanvasをクリックして追加してください。")

    def toggle_link_mode(self):
        self.mode = "link" if self.mode != "link" else "normal"
        self.link_mode_source = None
        self.link_btn.config(text="リンクモード ON" if self.mode == "link" else "リンクモード OFF")

    def on_canvas_click(self, event):
        tags = self.canvas.gettags(self.canvas.find_closest(event.x, event.y))
        node_id = next((t.split("_")[1] for t in tags if t.startswith("node_")), None)

        if self.mode == "add_node":
            self.add_node(event.x, event.y, self.current_node_type)
            self.mode = "normal"
        elif self.mode == "link" and node_id:
            if self.link_mode_source is None:
                self.link_mode_source = node_id
                messagebox.showinfo("リンク", f"最初のノード {self.nodes[node_id].name} が選択されました。次のノードをクリックしてください。")
            elif node_id != self.link_mode_source:
                self.add_link(self.link_mode_source, node_id)
                self.link_mode_source = None
        elif node_id:
            self.populate_edit_fields(node_id)

    def add_node(self, x, y, node_type):
        self.node_counters[node_type] += 1
        node_id = f"{node_type[:2]}{self.node_counters[node_type]}"
        name = f"{node_type}{self.node_counters[node_type]}"
        node = Node(node_id, x, y, node_type, name)
        self.nodes[node_id] = node
        self.draw_node(node)

    def get_radius(self, node_type):
        return {"コンビニ": 15, "スーパー": 20, "ホール": 25, "陣地": 30, "中心大厦": 35}.get(node_type, 15)

    def draw_node(self, node):
        w = self.get_radius(node.type) * 2
        h = self.get_radius(node.type)
        cx, cy = node.x, node.y
        rect_id = self.canvas.create_rectangle(cx - w//2, cy - h//2, cx + w//2, cy + h//2,
                                               fill="white", outline="black", width=2,
                                               tags=(f"node_{node.id}", "node"))
        text_id = self.canvas.create_text(cx, cy, text=node.name, tags=(f"node_{node.id}", "node_text"))
        node.circle_id = rect_id
        node.text_id = text_id
        for item in (rect_id, text_id):
            self.canvas.tag_bind(item, "<Button-1>", self.on_node_press)
            self.canvas.tag_bind(item, "<B1-Motion>", self.on_drag)
            self.canvas.tag_bind(item, "<ButtonRelease-1>", self.end_drag)

    def on_node_press(self, event):
        item = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(item)
        node_id = next((t.split("_")[1] for t in tags if t.startswith("node_")), None)
        if node_id:
            self.drag_data["node"] = self.nodes[node_id]
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            if self.mode == "normal":
                self.populate_edit_fields(node_id)

    def on_drag(self, event):
        if self.drag_data["node"]:
            dx, dy = event.x - self.drag_data["x"], event.y - self.drag_data["y"]
            node = self.drag_data["node"]
            for item in [node.circle_id, node.text_id]:
                self.canvas.move(item, dx, dy)
            node.x += dx
            node.y += dy
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.update_links_for_node(node.id)

    def end_drag(self, event):
        self.drag_data["node"] = None

    def add_link(self, id1, id2):
        n1, n2 = self.nodes[id1], self.nodes[id2]
        if id2 not in n1.links:
            n1.links.append(id2)
        if id1 not in n2.links:
            n2.links.append(id1)
        line = self.canvas.create_line(n1.x, n1.y, n2.x, n2.y, fill="black", width=2)
        self.links_lines[tuple(sorted([id1, id2]))] = line

    def update_links_for_node(self, node_id):
        node = self.nodes[node_id]
        for other_id in node.links:
            key = tuple(sorted([node_id, other_id]))
            if key in self.links_lines:
                other = self.nodes[other_id]
                self.canvas.coords(self.links_lines[key], node.x, node.y, other.x, other.y)

    def populate_edit_fields(self, node_id):
        node = self.nodes[node_id]
        self.edit_node_id = node_id
        self.name_var.set(node.name)
        self.score_var.set(str(node.score))

    def update_node_info(self):
        if not self.edit_node_id:
            return
        node = self.nodes[self.edit_node_id]
        node.name = self.name_var.get()
        try:
            node.score = int(self.score_var.get())
        except ValueError:
            node.score = 0
        self.canvas.itemconfigure(node.text_id, text=node.name)

    def save_map(self):
        self.update_territory_colors()
        data = {"bases": {
            node.id: {
                "name": node.name,
                "type": node.type,
                "x": node.x,
                "y": node.y,
                "score": node.score,
                "links": node.links,
                "assigned_color": node.assigned_color
            } for node in self.nodes.values()
        }}
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSONファイル", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存", f"マップが {path} に保存されました。")

    def load_map(self):
        path = filedialog.askopenfilename(defaultextension=".json", filetypes=[("JSONファイル", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clear_canvas()
            for node_id, info in data.get("bases", {}).items():
                node = Node(node_id, info["x"], info["y"], info["type"], info["name"], info.get("score", 0))
                node.links = info.get("links", [])
                node.assigned_color = info.get("assigned_color")
                self.nodes[node_id] = node
                self.draw_node(node)
            for node in self.nodes.values():
                for other_id in node.links:
                    key = tuple(sorted([node.id, other_id]))
                    if key not in self.links_lines and other_id in self.nodes:
                        self.add_link(node.id, other_id)
            messagebox.showinfo("読込", f"マップが {path} から読込まれました。")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.nodes = {}
        self.node_counters = {"コンビニ": 0, "スーパー": 0, "ホール": 0, "陣地": 0, "中心大厦": 0}
        self.links_lines = {}

    def update_territory_colors(self):
        territories = [n for n in self.nodes.values() if n.type == "陣地"]
        if not territories:
            return
        avg_x = sum(n.x for n in territories) / len(territories)
        avg_y = sum(n.y for n in territories) / len(territories)
        for n in territories:
            dx, dy = n.x - avg_x, avg_y - n.y
            angle = math.degrees(math.atan2(dx, dy)) % 360
            n.angle = angle
        territories.sort(key=lambda n: n.angle)
        for i, n in enumerate(territories):
            color = TERRITORY_COLORS[i % len(TERRITORY_COLORS)]
            n.assigned_color = color
            self.canvas.itemconfigure(n.circle_id, fill=color)

if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
