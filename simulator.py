# simulator_app.py - 陣取りシミュレーション（owner_team固定＆得点ロジック強化）
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
import json

NODE_SIZES = {
    "コンビニ": 15,
    "スーパー": 20,
    "ホール": 25,
    "陣地": 30,
    "中心大厦": 35
}

TERRITORY_COLORS = ["yellow", "red", "orange", "blue", "lightblue", "purple", "lightyellow", "magenta"]
TERRITORY_IDS = ["陣地A", "陣地B", "陣地C", "陣地D", "陣地E", "陣地F", "陣地G", "陣地H"]

class Node:
    def __init__(self, node_id, info):
        self.id = node_id
        self.name = info["name"]
        self.original_name = info["name"]
        self.type = info["type"]
        self.x = info["x"]
        self.y = info["y"]
        self.score = info["score"]
        self.links = info["links"]
        self.assigned_color = info.get("assigned_color")
        self.team = None
        self.owner_team = None  # 初期占領チーム（固定）
        self.rect_id = None
        self.text_id = None

class TerritorySimulator:
    def __init__(self, root, map_path):
        self.root = root
        self.root.title("陣取りシミュレーション")
        self.root.geometry("1280x720")
        self.nodes = {}
        self.teams = {}
        self.team_colors = {}

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=4)
        self.root.columnconfigure(1, weight=1)

        self.main_frame = ttk.Frame(root)
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=4)
        self.main_frame.columnconfigure(1, weight=1)

        self.canvas = tk.Canvas(self.main_frame, bg="white")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self.redraw_all)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.right_frame = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.right_panel = ttk.Frame(self.right_frame)
        self.right_panel.pack_propagate(False)

        ttk.Label(self.right_panel, text="占領状況").pack(pady=10)
        self.status = tk.Text(self.right_panel, wrap="none", height=30, font=("Courier", 10))
        self.status.pack(fill=tk.BOTH, expand=True)

        self.right_frame.add(self.right_panel, weight=1)

        self.load_map(map_path)
        self.draw_all()
        self.update_status()

    def load_map(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for nid, info in data["bases"].items():
            self.nodes[nid] = Node(nid, info)

    def draw_all(self):
        self.canvas.delete("all")
        for node in self.nodes.values():
            for link in node.links:
                if link in self.nodes:
                    x1, y1 = node.x, node.y
                    x2, y2 = self.nodes[link].x, self.nodes[link].y
                    self.canvas.create_line(x1, y1, x2, y2, fill="gray")
        for node in self.nodes.values():
            self.draw_node(node)

    def redraw_all(self, event):
        self.draw_all()
        self.update_status()

    def draw_node(self, node):
        w = NODE_SIZES.get(node.type, 15) * 2
        h = NODE_SIZES.get(node.type, 15)
        x, y = node.x, node.y
        color = self.team_colors.get(node.team, node.assigned_color if node.assigned_color else "white")
        node.rect_id = self.canvas.create_rectangle(x - w//2, y - h//2, x + w//2, y + h//2,
                                                    fill=color, outline="black", width=2,
                                                    tags=(f"node_{node.id}",))
        label = node.team if node.type == "陣地" and node.team else node.name

        for fs in range(16, 4, -1):
            fnt = font.Font(family="Arial", size=fs)
            if fnt.measure(label) <= w * 0.9:
                break
        node.text_id = self.canvas.create_text(x, y, text=label, font=("Arial", fs))

    def on_canvas_click(self, event):
        for node in self.nodes.values():
            x, y = node.x, node.y
            w = NODE_SIZES.get(node.type, 15) * 2
            h = NODE_SIZES.get(node.type, 15)
            if (x - w//2 <= event.x <= x + w//2) and (y - h//2 <= event.y <= y + h//2):
                self.assign_team(node)
                break

    def assign_team(self, node):
        win = tk.Toplevel(self.root)
        win.title(f"{node.name} 占領チーム選択")
        tk.Label(win, text="チーム選択:").pack()

        if node.type == "陣地" and not node.team:
            name = simpledialog.askstring("チーム名入力", f"{node.name} の初期チーム名を入力:", parent=self.root)
            if name:
                node.team = name
                if node.owner_team is None:
                    node.owner_team = name  # 初期のみ保存
                if name not in self.team_colors:
                    if node.name in TERRITORY_IDS:
                        idx = TERRITORY_IDS.index(node.name)
                        self.team_colors[name] = TERRITORY_COLORS[idx % len(TERRITORY_COLORS)]
                    else:
                        self.team_colors[name] = TERRITORY_COLORS[len(self.team_colors) % len(TERRITORY_COLORS)]
                self.draw_all()
                self.update_status()
                win.destroy()
                return

        if not self.team_colors:
            tk.Label(win, text="※ 陣地に先にチーム名を設定してください").pack()
            return

        selected = tk.StringVar(value=node.team if node.team else list(self.team_colors.keys())[0])
        for name in self.team_colors:
            ttk.Radiobutton(win, text=name, variable=selected, value=name).pack(anchor="w")

        def confirm():
            node.team = selected.get()
            self.draw_all()
            self.update_status()
            win.destroy()

        ttk.Button(win, text="決定", command=confirm).pack(pady=5)

    def update_status(self):
        scores = {}
        for node in self.nodes.values():
            if node.team:
                scores[node.team] = 0  # 初期化

        for node in self.nodes.values():
            if node.team:
                if node.type == "陣地" and node.owner_team and node.team == node.owner_team:
                    continue  # 自陣スキップ
                scores[node.team] += node.score

        self.status.delete("1.0", tk.END)
        content = f"{'拠点名':<10} {'チーム':<10} {'得点':<5}\n" + "=" * 30 + "\n"
        for node in self.nodes.values():
            team = node.team if node.team else "-"
            content += f"{node.original_name:<10} {team:<10} {node.score:<5}\n"
        content += "\n[チーム別合計得点]\n"
        for name, score in scores.items():
            content += f"{name:<10}: {score} 点\n"
        self.status.configure(font=self.adjust_status_font(content))
        self.status.insert(tk.END, content)

    def adjust_status_font(self, content):
        for fs in range(12, 6, -1):
            f = font.Font(family="Courier", size=fs)
            lines = content.split("\n")
            if all(f.measure(line) < self.status.winfo_width() for line in lines):
                return ("Courier", fs)
        return ("Courier", 8)

if __name__ == "__main__":
    root = tk.Tk()
    app = TerritorySimulator(root, "map.json")
    root.mainloop()
