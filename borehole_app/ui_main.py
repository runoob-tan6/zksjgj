from __future__ import annotations

from pathlib import Path
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .models import Borehole, MAIN_FIELD_NAMES, ProjectData
from .project import borehole_type_from_prefix, copy_borehole, create_empty_project, create_new_borehole, is_borehole_prefix, load_project, next_borehole_prefix
from .settings import load_last_project, save_last_project
from .ui_basic_data import BasicDataFrame
from .ui_main_file import MainFileFrame
from .ui_raw_text import RawTextFrame, ValidationFrame
from .ui_test_data import TestDataFrame
from .undo import BoreholeSnapshot, UndoAction, UndoManager, copy_layers, copy_tests
from .validation import validate_project
from .writer import export_layer_test_summary, generate_dirty_boreholes


class BoreholeEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("钻孔数据编辑工具")
        self.minsize(980, 640)
        self.project: ProjectData = create_empty_project()
        self.current_borehole: Borehole | None = None
        self.undo_managers: dict[int, UndoManager] = {}
        self.busy = False
        self._build_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.confirm_close)
        self.bind_all("<Control-z>", self.handle_undo)
        self.bind_all("<Control-Z>", self.handle_undo)
        self.bind_all("<Control-y>", self.handle_redo)
        self.bind_all("<Control-Y>", self.handle_redo)
        self.load_last_project_on_start()
        self._center_window(1180, 760)
        self.deiconify()

    def _center_window(self, width: int, height: int) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_style(self) -> None:
        self.configure(bg="#F7F8FC")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background="#F7F8FC")
        style.configure("TFrame", background="#F7F8FC")
        style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        style.configure("TLabel", background="#F7F8FC", foreground="#20242A")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"), background="#F7F8FC", foreground="#20242A")
        style.configure("Hint.TLabel", foreground="#697386", background="#F7F8FC")
        style.configure("TButton", padding=(12, 7), background="#EEF2FF", foreground="#27315D", borderwidth=0)
        style.map("TButton", background=[("active", "#E0E7FF")])
        style.configure("Accent.TButton", padding=(14, 8), background="#6C63FF", foreground="#FFFFFF", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#5A52E0")])
        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#20242A", rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background="#F1F4FA", foreground="#3A4252", borderwidth=0, padding=(8, 8))
        style.map("Treeview", background=[("selected", "#E0E7FF")], foreground=[("selected", "#20242A")])
        style.configure("TNotebook", background="#F7F8FC", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9), background="#EEF2F7", foreground="#586174")
        style.map("TNotebook.Tab", background=[("selected", "#FFFFFF")], foreground=[("selected", "#20242A")])
        style.configure("TEntry", fieldbackground="#FFFFFF", borderwidth=1, padding=(8, 6))
        style.configure("TCombobox", fieldbackground="#FFFFFF", padding=(8, 6))

    def _build_ui(self) -> None:
        # 顶部工具栏（标题 + 项目名 + 操作按钮）
        top = ttk.Frame(self, padding=(16, 12))
        top.pack(fill="x")
        ttk.Label(top, text="钻孔数据编辑", style="Title.TLabel").pack(side="left")
        self.project_var = tk.StringVar(value="当前项目：未加载")
        ttk.Label(top, textvariable=self.project_var, style="Hint.TLabel", width=30).pack(side="left", padx=(16, 8))
        self.project_button = ttk.Button(top, text="选择项目", width=7, command=self.choose_project)
        self.project_button.pack(side="right", padx=4)
        self.reload_button = ttk.Button(top, text="重新加载", width=7, command=self.reload_project)
        self.reload_button.pack(side="right", padx=4)
        self.add_button = ttk.Button(top, text="新增钻孔", width=7, command=self.add_borehole)
        self.add_button.pack(side="right", padx=4)
        self.validate_button = ttk.Button(top, text="校验", width=4, command=self.validate_current_project)
        self.validate_button.pack(side="right", padx=4)
        self.export_button = ttk.Button(top, text="导出地层试验", width=10, command=self.export_layer_tests)
        self.export_button.pack(side="right", padx=4)
        self.save_button = ttk.Button(top, text="保存数据", width=7, style="Accent.TButton", command=self.generate_boreholes)
        self.save_button.pack(side="right", padx=4)
        self.redo_button = ttk.Button(top, text="恢复", width=4, command=self.redo)
        self.redo_button.pack(side="right", padx=4)
        self.undo_button = ttk.Button(top, text="撤销", width=4, command=self.undo)
        self.undo_button.pack(side="right", padx=4)

        body = ttk.Frame(self, padding=(16, 0, 16, 16))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, width=240)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        ttk.Label(left, text="钻孔列表", style="Title.TLabel").pack(anchor="w", pady=(4, 10))
        self.borehole_tree = ttk.Treeview(left, show="tree", height=22)
        self.borehole_tree.pack(fill="both", expand=True)
        self.borehole_tree.bind("<<TreeviewSelect>>", self.on_borehole_selected)
        self.borehole_tree.bind("<Button-3>", self.show_borehole_context_menu)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制钻孔", command=self.copy_selected_borehole)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除钻孔", command=self.delete_selected_borehole)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)
        self.main_file_frame = MainFileFrame(self.notebook, lambda: self.mark_current_dirty("main"), self.on_hole_id_changed, self.begin_borehole_change, self.end_borehole_change)
        self.basic_frame = BasicDataFrame(self.notebook, self.mark_current_dirty, self.begin_borehole_change, self.end_borehole_change)
        self.test_frame = TestDataFrame(self.notebook, self.mark_current_dirty, self.begin_borehole_change, self.end_borehole_change)
        self.raw_frame = RawTextFrame(self.notebook)
        self.validation_frame = ValidationFrame(self.notebook)
        self.notebook.add(self.main_file_frame, text="主文件")
        self.notebook.add(self.basic_frame, text="基础数据")
        self.notebook.add(self.test_frame, text="试验数据")
        self.notebook.add(self.raw_frame, text="原始文本")
        self.notebook.add(self.validation_frame, text="校验结果")
        status_bar = ttk.Frame(self, padding=(16, 0, 16, 10))
        status_bar.pack(fill="x")
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(status_bar, textvariable=self.status_var, style="Hint.TLabel").pack(side="left")
        self.project_summary_var = tk.StringVar(value="总深度：--    取样：0    标贯：0    注水：0    压水：0")
        ttk.Label(status_bar, textvariable=self.project_summary_var, style="Hint.TLabel").pack(side="right")
        self.update_undo_controls()

    def set_project_name(self, name: str) -> None:
        display_name = name if len(name) <= 18 else f"{name[:15]}..."
        self.project_var.set(f"当前项目：{display_name}")

    def load_last_project_on_start(self) -> None:
        last = load_last_project()
        if last and last.exists():
            self.load_project_path(last)
        else:
            self.set_empty_project("未加载项目。请选择项目文件夹。")

    def set_empty_project(self, message: str) -> None:
        self.project = create_empty_project()
        self.current_borehole = None
        self.undo_managers.clear()
        self.set_project_name("未加载")
        self.status_var.set(message)
        self.refresh_borehole_list()
        self.load_current_borehole(None)
        self.update_project_summary()
        self.update_undo_controls()

    def choose_project(self) -> None:
        if self.busy:
            return
        folder = filedialog.askdirectory(title="选择钻孔项目文件夹")
        if folder:
            self.load_project_path(Path(folder))

    def reload_project(self) -> None:
        if self.busy:
            return
        if self.project.folder:
            self.load_project_path(self.project.folder)
        else:
            self.set_empty_project("当前没有项目可重新加载。")

    def load_project_path(self, folder: Path) -> None:
        if self.busy:
            return
        self.set_busy(True)
        self.status_var.set(f"正在加载项目：{folder.name}...")

        def worker() -> None:
            project = load_project(folder)
            self.after(0, lambda: self.finish_load_project(folder, project))

        threading.Thread(target=worker, daemon=True).start()

    def finish_load_project(self, folder: Path, project: ProjectData) -> None:
        self.set_busy(False)
        if project.load_error:
            self.set_empty_project(project.load_error)
            return
        self.project = project
        self.undo_managers.clear()
        self.current_borehole = None
        save_last_project(folder)
        self.set_project_name(folder.name)
        self.status_var.set(f"已加载 {len(project.boreholes)} 个钻孔。")
        self.refresh_borehole_list()
        first = self.project.sorted_boreholes()[0] if self.project.boreholes else None
        self.load_current_borehole(first)
        if first:
            self.select_borehole_in_tree(first.prefix)
        self.update_project_summary()
        self.update_undo_controls()

    def refresh_borehole_list(self) -> None:
        selection = self.borehole_tree.selection()
        selected_prefix = selection[0] if selection else None
        self.borehole_tree.delete(*self.borehole_tree.get_children())
        zk = self.borehole_tree.insert("", "end", text="岩钻孔 ZK", open=True)
        nzk = self.borehole_tree.insert("", "end", text="土钻孔 NZK", open=True)
        for borehole in self.project.sorted_boreholes():
            parent = nzk if borehole.hole_type == "NZK" else zk
            self.borehole_tree.insert(parent, "end", iid=borehole.prefix, text=borehole.display_name())
        if selected_prefix and self.borehole_tree.exists(selected_prefix):
            self.select_borehole_in_tree(selected_prefix)

    def select_borehole_in_tree(self, prefix: str) -> None:
        if self.borehole_tree.exists(prefix):
            self.borehole_tree.selection_set(prefix)
            self.borehole_tree.focus(prefix)

    def on_borehole_selected(self, _event=None) -> None:
        selection = self.borehole_tree.selection()
        if not selection:
            return
        key = selection[0]
        if key in self.project.boreholes:
            borehole = self.project.boreholes[key]
            if self.current_borehole is borehole:
                return  # 同一钻孔，跳过重载
            self.load_current_borehole(borehole)

    def show_borehole_context_menu(self, event) -> None:
        item = self.borehole_tree.identify_row(event.y)
        if not item or item not in self.project.boreholes:
            return
        self.borehole_tree.selection_set(item)
        self.borehole_tree.focus(item)
        self.load_current_borehole(self.project.boreholes[item])
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def copy_selected_borehole(self) -> None:
        selection = self.borehole_tree.selection()
        if not selection:
            return
        source_prefix = selection[0]
        if source_prefix not in self.project.boreholes:
            return
        default_prefix = next_borehole_prefix(self.project, source_prefix)
        new_prefix = simpledialog.askstring("复制钻孔", "请输入新钻孔编号：", initialvalue=default_prefix)
        if not new_prefix:
            return
        new_prefix = new_prefix.strip()
        if not is_borehole_prefix(new_prefix):
            messagebox.showwarning("提示", "钻孔编号格式不正确。请输入 ZK、NZK 开头，后接可选字母、数字和连字符，例如 ZK1、ZK2-1、ZKB1、NZK3-1、NZKB1-1。")
            return
        if new_prefix in self.project.boreholes:
            messagebox.showwarning("提示", f"钻孔 {new_prefix} 已存在。")
            return
        borehole = copy_borehole(self.project, self.project.boreholes[source_prefix], new_prefix)
        self.get_undo_manager(borehole)
        self.refresh_borehole_list()
        self.load_current_borehole(borehole)
        self.select_borehole_in_tree(new_prefix)
        self.update_project_summary()

    def delete_selected_borehole(self) -> None:
        selection = self.borehole_tree.selection()
        if not selection:
            return
        prefix = selection[0]
        borehole = self.project.boreholes.get(prefix)
        if not borehole:
            return
        if not messagebox.askyesno("删除钻孔", f"确定删除钻孔 {prefix}？\n\n点击保存数据后，会备份并删除该钻孔的所有原始文件。"):
            return
        self.project.boreholes.pop(prefix, None)
        if not borehole.is_new:
            self.project.deleted_boreholes[prefix] = borehole
        self.undo_managers.pop(id(borehole), None)
        next_borehole = self.project.sorted_boreholes()[0] if self.project.boreholes else None
        self.refresh_borehole_list()
        self.load_current_borehole(next_borehole)
        if next_borehole:
            self.select_borehole_in_tree(next_borehole.prefix)
        self.status_var.set(f"已删除钻孔 {prefix}，点击保存数据写入删除操作。")
        self.update_project_summary()
        self.update_undo_controls()

    def load_current_borehole(self, borehole: Borehole | None) -> None:
        self.current_borehole = borehole
        self.main_file_frame.load_borehole(borehole)
        self.basic_frame.load_borehole(borehole)
        self.test_frame.load_borehole(borehole)
        self.raw_frame.load_borehole(borehole)
        self.validation_frame.load_borehole(borehole)
        if borehole:
            self.status_var.set(f"当前钻孔：{borehole.prefix}")
        self.update_undo_controls()

    def mark_current_dirty(self, suffix: str | None = None) -> None:
        if self.current_borehole:
            self.current_borehole.mark_dirty(suffix)
            self.update_project_summary()
            prefix = self.current_borehole.prefix
            if self.borehole_tree.exists(prefix):
                self.borehole_tree.item(prefix, text=self.current_borehole.display_name())
            self.status_var.set(f"{self.current_borehole.prefix} 已修改，点击保存数据写入变化文件。")

    def update_project_summary(self) -> None:
        total_depth = 0.0
        counts = {"o": 0, "q": 0, "n": 0, "m": 0}
        for borehole in self.project.boreholes.values():
            try:
                total_depth += float(borehole.main.depth.strip())
            except ValueError:
                pass
            for suffix in counts:
                records = borehole.tests.get(suffix, [])
                counts[suffix] += sum(1 for record in records if any(str(value).strip() for value in record.values))
        depth_text = f"{total_depth:g}" if total_depth else "--"
        text = f"总深度：{depth_text} m    取样：{counts['o']}    标贯：{counts['q']}    注水：{counts['n']}    压水：{counts['m']}"
        self.project_summary_var.set(text)

    def _borehole_key(self, borehole: Borehole | None) -> int | None:
        if not borehole:
            return None
        return id(borehole)

    def get_undo_manager(self, borehole: Borehole | None) -> UndoManager | None:
        key = self._borehole_key(borehole)
        if key is None:
            return None
        if key not in self.undo_managers:
            self.undo_managers[key] = UndoManager(max_depth=100)
        return self.undo_managers[key]

    def begin_borehole_change(self, borehole: Borehole | None, label: str):
        if not borehole:
            return None
        return {"borehole": borehole, "label": label, "before": BoreholeSnapshot.capture(borehole)}

    def end_borehole_change(self, token) -> None:
        if not token:
            return
        borehole = token["borehole"]
        before = token["before"]
        after = BoreholeSnapshot.capture(borehole)
        if before.same_content(after):
            return
        manager = self.get_undo_manager(borehole)
        if manager:
            manager.push(UndoAction(borehole=borehole, label=token["label"], before=before, after=after))
        self.update_undo_controls()

    def flush_active_editors(self) -> None:
        for frame in (self.main_file_frame, self.basic_frame, self.test_frame):
            commit = getattr(frame, "commit_active_edit", None)
            if commit:
                commit()

    def handle_undo(self, _event=None):
        self.flush_active_editors()
        self.undo()
        return "break"

    def handle_redo(self, _event=None):
        self.flush_active_editors()
        self.redo()
        return "break"

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button_name in ("project_button", "reload_button", "add_button", "validate_button", "export_button", "save_button"):
            button = getattr(self, button_name, None)
            if button:
                button.configure(state=state)
        if hasattr(self, "borehole_tree"):
            self.borehole_tree.configure(selectmode="none" if busy else "browse")
        self.update_undo_controls()

    def update_undo_controls(self) -> None:
        manager = self.get_undo_manager(self.current_borehole)
        can_undo = manager.can_undo() if manager else False
        can_redo = manager.can_redo() if manager else False
        if self.busy:
            can_undo = False
            can_redo = False
        if hasattr(self, "undo_button"):
            self.undo_button.configure(state="normal" if can_undo else "disabled")
        if hasattr(self, "redo_button"):
            self.redo_button.configure(state="normal" if can_redo else "disabled")

    def apply_borehole_snapshot(self, borehole: Borehole, snapshot: BoreholeSnapshot) -> None:
        old_key = borehole.prefix
        if old_key in self.project.boreholes and self.project.boreholes[old_key] is borehole:
            del self.project.boreholes[old_key]
        borehole.prefix = snapshot.prefix
        borehole.hole_type = snapshot.hole_type
        borehole.main.lines = list(snapshot.main_lines)
        borehole.layers = copy_layers(snapshot.layers)
        borehole.tests = copy_tests(snapshot.tests)
        borehole.dirty = snapshot.dirty
        borehole.dirty_suffixes = set(snapshot.dirty_suffixes)
        borehole.is_new = snapshot.is_new
        borehole.old_prefix = snapshot.old_prefix
        self.project.boreholes[borehole.prefix] = borehole
        self.current_borehole = borehole
        self.refresh_borehole_list()
        self.load_current_borehole(borehole)
        self.select_borehole_in_tree(borehole.prefix)
        self.update_undo_controls()

    def undo(self) -> None:
        manager = self.get_undo_manager(self.current_borehole)
        if not manager:
            return
        action = manager.pop_undo()
        if not action:
            return
        self.apply_borehole_snapshot(action.borehole, action.before)
        manager.push_redo(action)
        self.status_var.set(f"已撤销：{action.label}")
        self.update_undo_controls()
        self._switch_tab_by_label(action.label)

    def redo(self) -> None:
        manager = self.get_undo_manager(self.current_borehole)
        if not manager:
            return
        action = manager.pop_redo()
        if not action:
            return
        self.apply_borehole_snapshot(action.borehole, action.after)
        manager.push_undo_without_clearing_redo(action)
        self.status_var.set(f"已恢复：{action.label}")
        self.update_undo_controls()
        self._switch_tab_by_label(action.label)

    def _switch_tab_by_label(self, label: str) -> None:
        """根据撤销/恢复的 label 跳转到对应的 tab 和位置"""
        if "主文件" in label:
            self.notebook.select(0)
            match = re.search(r"修改主文件[：:](.+)", label)
            if match:
                field_name = match.group(1).strip()
                for index, name in enumerate(MAIN_FIELD_NAMES):
                    if name == field_name and index in self.main_file_frame.entries:
                        self.main_file_frame.entries[index].focus_set()
                        break
        elif "基础数据" in label:
            self.notebook.select(1)
            match = re.search(r"第\s*(\d+)\s*行", label)
            if match:
                self.basic_frame.select_inserted_layer(int(match.group(1)) - 1)
        elif "试验数据" in label:
            self.notebook.select(2)
            suffix_match = re.search(r"\.\-(\w)", label)
            row_match = re.search(r"第\s*(\d+)\s*行", label)
            if suffix_match and row_match:
                section = self.test_frame.sections.get(suffix_match.group(1))
                if section:
                    section.select_record(int(row_match.group(1)) - 1)

    def on_hole_id_changed(self, old_prefix: str, new_prefix: str) -> None:
        if old_prefix == new_prefix:
            return
        if not is_borehole_prefix(new_prefix):
            messagebox.showwarning("提示", "钻孔编号格式不正确。请输入 ZK、NZK 开头，后接可选字母、数字和连字符，例如 ZK1、ZK2-1、ZKB1、NZK3-1、NZKB1-1。")
            self.main_file_frame.set_hole_id(old_prefix)
            return
        if new_prefix in self.project.boreholes:
            messagebox.showwarning("提示", f"钻孔编号 {new_prefix} 已存在。")
            self.main_file_frame.set_hole_id(old_prefix)
            return
        borehole = self.project.boreholes.pop(old_prefix)
        borehole.old_prefix = old_prefix
        borehole.mark_dirty("main")
        borehole.prefix = new_prefix
        borehole.hole_type = borehole_type_from_prefix(new_prefix)
        self.project.boreholes[new_prefix] = borehole
        self.current_borehole = borehole
        if self.borehole_tree.exists(old_prefix):
            parent = self.borehole_tree.parent(old_prefix)
            self.borehole_tree.delete(old_prefix)
            self.borehole_tree.insert(parent, "end", iid=new_prefix, text=borehole.display_name())
            self.borehole_tree.selection_set(new_prefix)
            self.borehole_tree.focus(new_prefix)
        self.status_var.set(f"当前钻孔：{new_prefix}")
        self.update_project_summary()

    def add_borehole(self) -> None:
        if not self.project.folder:
            messagebox.showinfo("提示", "请先选择项目文件夹。")
            return
        prefix = simpledialog.askstring("新增钻孔", "请输入钻孔编号，例如 ZK8 或 NZK13：")
        if not prefix:
            return
        prefix = prefix.strip()
        if not is_borehole_prefix(prefix):
            messagebox.showwarning("提示", "钻孔编号格式不正确。请输入 ZK、NZK 开头，后接可选字母、数字和连字符，例如 ZK1、ZK2-1、ZKB1、NZK3-1、NZKB1-1。")
            return
        if prefix in self.project.boreholes:
            messagebox.showwarning("提示", f"钻孔 {prefix} 已存在。")
            return
        borehole = create_new_borehole(self.project, prefix)
        self.get_undo_manager(borehole)
        self.refresh_borehole_list()
        self.load_current_borehole(borehole)
        self.select_borehole_in_tree(prefix)
        self.update_project_summary()

    def export_layer_tests(self) -> None:
        if not self.project.folder:
            messagebox.showinfo("提示", "请先选择项目文件夹。")
            return
        default_name = f"{self.project.folder.name}_地层试验汇总.csv"
        path = filedialog.asksaveasfilename(
            title="导出地层试验汇总",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        self.status_var.set("正在导出地层试验汇总...")
        export_path = Path(path)

        def worker() -> None:
            try:
                row_count = export_layer_test_summary(self.project, export_path)
            except OSError as exc:
                error_message = str(exc)
                self.after(0, lambda: messagebox.showerror("导出失败", error_message))
                self.after(0, lambda: self.status_var.set("导出地层试验汇总失败。"))
                return
            self.after(0, lambda: self.status_var.set(f"已导出地层试验汇总：{row_count} 行。"))
            self.after(0, lambda: messagebox.showinfo("导出完成", f"已导出 {row_count} 行地层试验数据。\n{export_path}"))

        threading.Thread(target=worker, daemon=True).start()

    def validate_current_project(self) -> None:
        messages = validate_project(self.project)
        if not messages:
            messagebox.showinfo("校验结果", "未发现明显问题。")
            self.status_var.set("校验完成：未发现明显问题。")
        else:
            messagebox.showwarning("校验结果", "\n".join(messages[:20]) + ("\n..." if len(messages) > 20 else ""))
            self.status_var.set(f"校验完成：发现 {len(messages)} 项问题。")
        self.validation_frame.load_borehole(self.current_borehole)

    def generate_boreholes(self) -> None:
        if self.busy:
            return
        self.flush_active_editors()
        dirty = self.project.dirty_boreholes()
        deleted = list(self.project.deleted_boreholes)
        if not dirty and not deleted:
            messagebox.showinfo("保存数据", "没有新增、修改或删除的钻孔需要保存。")
            return
        prompt_parts = []
        if dirty:
            prompt_parts.append("将保存以下新增或已修改钻孔：\n" + "\n".join(b.prefix for b in dirty))
        if deleted:
            prompt_parts.append("将删除以下钻孔文件（删除前自动备份到 tmp 文件夹）：\n" + "\n".join(deleted))
        prompt = "\n\n".join(prompt_parts)
        if not messagebox.askyesno("保存数据", f"{prompt}\n\n未变化文件不会重复写入。\n是否继续？"):
            return
        selected_prefix = self.current_borehole.prefix if self.current_borehole else None
        self.set_busy(True)
        self.status_var.set("正在保存数据...")

        def worker() -> None:
            try:
                generated = generate_dirty_boreholes(self.project)
            except OSError as exc:
                error_message = str(exc)
                self.after(0, lambda: self.finish_generate_boreholes(None, selected_prefix, error_message))
                return
            self.after(0, lambda: self.finish_generate_boreholes(generated, selected_prefix, None))

        threading.Thread(target=worker, daemon=True).start()

    def finish_generate_boreholes(self, generated: list[Path] | None, selected_prefix: str | None, error_message: str | None) -> None:
        self.set_busy(False)
        if error_message:
            self.status_var.set("保存失败。")
            messagebox.showerror("保存失败", error_message)
            return
        generated = generated or []
        self.undo_managers.clear()
        self.refresh_borehole_list()
        if selected_prefix and selected_prefix in self.project.boreholes:
            self.load_current_borehole(self.project.boreholes[selected_prefix])
            self.select_borehole_in_tree(selected_prefix)
        self.update_project_summary()
        self.update_undo_controls()
        self.status_var.set(f"已保存，实际更新 {len(generated)} 个文件。")
        messagebox.showinfo("保存完成", f"保存完成，实际更新 {len(generated)} 个文件。")

    def has_unsaved_changes(self) -> bool:
        return bool(self.project.dirty_boreholes() or self.project.deleted_boreholes)

    def confirm_close(self) -> None:
        if self.has_unsaved_changes():
            prompt = "存在未保存的数据修改，确定退出？"
        else:
            prompt = "确定关闭软件？"
        if messagebox.askyesno("关闭确认", prompt):
            self.destroy()


def main() -> None:
    app = BoreholeEditorApp()
    app.mainloop()
