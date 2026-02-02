import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
from datetime import datetime
import shutil
import webbrowser
from io import StringIO
import csv

INVENTORY_FILE = 'inventory.json'
BACKUP_DIR = 'backups'

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartInventory Pro - Peta's Edition")
        self.root.geometry("1000x860")
        self.root.minsize(1000, 700)

        self.dark_mode = tk.BooleanVar(value=False)
        self.style = ttk.Style()
        self.inventory = self.load_inventory()
        self.selected_item = None
        self.active_filter = "all"

        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Main container
        main = ttk.Frame(root, padding="20 15 20 15")
        main.pack(fill=tk.BOTH, expand=True)

        # ─── Scrollable area ───────────────────────────────────────
        canvas = tk.Canvas(main)
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # TOP BAR
        top = ttk.Frame(scrollable_frame)
        top.pack(fill=tk.X, pady=(0, 16))

        ttk.Label(top, text="SmartInventory Pro", font=("Segoe UI", 24, "bold")).pack(side=tk.LEFT)

        self.stats_label = ttk.Label(top, font=("Segoe UI", 13), foreground="#555")
        self.stats_label.pack(side=tk.LEFT, padx=40)

        ttk.Checkbutton(top, text="Dark Mode", variable=self.dark_mode,
                        command=self.toggle_theme).pack(side=tk.RIGHT)

        # FILTER BAR
        filter_bar = ttk.Frame(scrollable_frame)
        filter_bar.pack(fill=tk.X, pady=(0, 16))

        for text, mode in [
            ("All", "all"),
            ("Low Stock", "low"),
            ("Out of Stock", "zero"),
            ("Recently Updated", "recent")
        ]:
            ttk.Button(filter_bar, text=text, width=14,
                       command=lambda m=mode: self.apply_filter(m)).pack(side=tk.LEFT, padx=3)

        ttk.Label(filter_bar, text="Search:").pack(side=tk.LEFT, padx=(30, 6))
        self.search_var = tk.StringVar()
        ttk.Entry(filter_bar, textvariable=self.search_var, width=28).pack(side=tk.LEFT)
        self.search_var.trace("w", lambda *args: self.refresh_list())

        # TREEVIEW
        tree_frame = ttk.Frame(scrollable_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        columns = ("name", "qty", "low", "price", "total", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=16)
        
        for col, txt, w in zip(columns, ["Item Name", "Qty", "Low @", "Price", "Total Value", "Status"],
                               [340, 80, 80, 110, 130, 110]):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center" if col != "name" else "w")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_item_select)

        # EDIT PANEL
        edit = ttk.LabelFrame(scrollable_frame, text=" Selected Item ", padding="16 20")
        edit.pack(fill=tk.X, pady=(0, 16))

        ttk.Label(edit, text="Item:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.name_label = ttk.Label(edit, text="", width=45, relief="sunken", anchor="w", padding=6)
        self.name_label.grid(row=0, column=1, columnspan=5, sticky="ew", pady=6)

        ttk.Label(edit, text="Quantity:").grid(row=1, column=0, sticky="e", padx=8, pady=8)
        qty_frame = ttk.Frame(edit)
        qty_frame.grid(row=1, column=1, columnspan=5, sticky="w", pady=8)

        for delta, txt in [(-10, "−10"), (-1, "−1"), (1, "+1"), (10, "+10")]:
            ttk.Button(qty_frame, text=txt, width=6,
                       command=lambda d=delta: self.change_qty(d)).pack(side=tk.LEFT, padx=4)

        self.qty_entry = ttk.Entry(qty_frame, width=12, justify="center", font=("Segoe UI", 12, "bold"))
        self.qty_entry.pack(side=tk.LEFT, padx=12)
        self.qty_entry.bind('<Return>', lambda e: self.update_item())

        ttk.Label(edit, text="Price:").grid(row=2, column=0, sticky="e", padx=8, pady=8)
        self.price_entry = ttk.Entry(edit, width=14)
        self.price_entry.grid(row=2, column=1, sticky="w", pady=8)

        ttk.Label(edit, text="Low Alert @").grid(row=2, column=2, sticky="e", padx=(20,8), pady=8)
        self.low_entry = ttk.Entry(edit, width=10)
        self.low_entry.grid(row=2, column=3, sticky="w", pady=8)

        ttk.Label(edit, text="Note:").grid(row=3, column=0, sticky="e", padx=8, pady=8)
        self.note_entry = ttk.Entry(edit, width=60)
        self.note_entry.grid(row=3, column=1, columnspan=5, sticky="ew", pady=8)

        btn_frame = ttk.Frame(edit)
        btn_frame.grid(row=4, column=0, columnspan=6, pady=16, sticky="w")

        ttk.Button(btn_frame, text="Add New Item", command=self.add_item).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Update Item", command=self.update_item).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Delete Item", command=self.remove_item).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Print", command=self.print_table).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Report", command=self.generate_report).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Backup", command=self.backup_inventory).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Restore", command=self.restore_inventory).pack(side=tk.LEFT, padx=6)

        # HISTORY
        hist_frame = ttk.LabelFrame(scrollable_frame, text="Recent Movements (last 5)", padding=12)
        hist_frame.pack(fill=tk.BOTH, pady=(0, 8), expand=True)

        self.history = tk.Text(hist_frame, height=7, state=tk.DISABLED, wrap=tk.WORD)
        self.history.pack(fill=tk.BOTH, expand=True)

        # STATUS BAR
        status_frame = ttk.Frame(scrollable_frame)
        status_frame.pack(fill=tk.X, pady=(8, 0))

        self.status_var = tk.StringVar(value=" Ready – Select an item or add new")
        ttk.Label(status_frame, textvariable=self.status_var, relief="sunken", anchor="w", padding=6).pack(fill=tk.X)

        self.apply_theme()
        self.refresh_list()
        self.update_stats()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ──────────────────────────────────────────────
    # THEME
    # ──────────────────────────────────────────────
    def apply_theme(self):
        if self.dark_mode.get():
            bg = "#1e1e1e"
            fg = "#f0f0f0"
            tree_bg = "#252525"
            tree_fg = "#f0f0f0"
            select_bg = "#404060"
            heading_bg = "#333344"
            heading_fg = "#000000"
            entry_bg = "#2d2d2d"
            low_fg = "#ff7777"
            button_fg = "#000000"

            self.root.configure(bg=bg)
            self.style.configure(".", background=bg, foreground=fg)
            self.style.configure("Treeview", background=tree_bg, foreground=tree_fg, fieldbackground=tree_bg)
            self.style.map("Treeview", background=[("selected", select_bg)], foreground=[("selected", "white")])
            self.style.configure("Treeview.Heading", background=heading_bg, foreground=heading_fg)
            self.style.configure("TButton", foreground=button_fg, background="#444444")
            self.style.configure("TLabel", foreground=fg)
            self.style.configure("TEntry", foreground=fg, fieldbackground=entry_bg)
            self.style.configure("TCheckbutton", foreground=fg)
            self.style.configure("TLabelframe.Label", foreground=fg)
            self.style.configure("LowStock.Treeview", foreground=low_fg)

            if hasattr(self, 'history'):
                self.history.config(bg="#252525", fg="#f0f0f0", insertbackground="#f0f0f0")
        else:
            bg = "#f8f9fa"
            fg = "#000000"
            tree_bg = "white"
            tree_fg = "#000000"
            select_bg = "#d0e0ff"
            heading_bg = "#4a90e2"
            heading_fg = "#000000"
            entry_bg = "white"
            low_fg = "#d32f2f"
            button_fg = "#000000"

            self.root.configure(bg=bg)
            self.style.configure(".", background=bg, foreground=fg)
            self.style.configure("Treeview", background=tree_bg, foreground=tree_fg, fieldbackground=tree_bg)
            self.style.map("Treeview", background=[("selected", select_bg)], foreground=[("selected", "black")])
            self.style.configure("Treeview.Heading", background=heading_bg, foreground=heading_fg)
            self.style.configure("TButton", foreground=button_fg)
            self.style.configure("TLabel", foreground=fg)
            self.style.configure("TEntry", foreground=fg, fieldbackground=entry_bg)
            self.style.configure("TCheckbutton", foreground=fg)
            self.style.configure("TLabelframe.Label", foreground=fg)
            self.style.configure("LowStock.Treeview", foreground=low_fg)

            if hasattr(self, 'history'):
                self.history.config(bg="white", fg="black", insertbackground="black")

    def toggle_theme(self):
        self.apply_theme()
        self.refresh_list()

    # ──────────────────────────────────────────────
    # CORE LOGIC
    # ──────────────────────────────────────────────
    def load_inventory(self):
        if os.path.exists(INVENTORY_FILE):
            try:
                with open(INVENTORY_FILE, 'r') as f:
                    data = json.load(f)
                    for item in data.values():
                        item.setdefault("history", [])
                        item.setdefault("low_threshold", 5)
                    return data
            except:
                return {}
        return {}

    def refresh_list(self, *args):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().lower().strip()

        for name, d in sorted(self.inventory.items()):
            qty = d["quantity"]
            low = d.get("low_threshold", 5)
            price = d["price"]
            status = "LOW" if qty <= low else ""

            if self.active_filter == "low" and qty > low: continue
            if self.active_filter == "zero" and qty != 0: continue
            if self.active_filter == "recent":
                if not d["history"]: continue
                last = datetime.strptime(d["history"][-1]["date"], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last).days > 7: continue

            if search and search not in name.lower():
                continue

            tags = ("lowstock",) if status == "LOW" else ()
            self.tree.insert("", "end", iid=name,
                             values=(name, qty, low, f"${price:.2f}", f"${qty*price:.2f}", status),
                             tags=tags)

        self.tree.tag_configure("lowstock", foreground="#d32f2f" if not self.dark_mode.get() else "#ff7777")

    def apply_filter(self, mode):
        self.active_filter = mode
        self.refresh_list()

    # ──────────────────────────────────────────────
    # ITEM ACTIONS
    # ──────────────────────────────────────────────
    def on_item_select(self, event):
        sel = self.tree.selection()
        if not sel:
            self.clear_edit_fields()
            self.history.config(state="normal")
            self.history.delete("1.0", "end")
            self.history.config(state="disabled")
            return

        name = sel[0]
        d = self.inventory[name]

        self.selected_item = name
        self.name_label.config(text=name)
        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, str(d["quantity"]))
        self.price_entry.delete(0, "end")
        self.price_entry.insert(0, f"{d['price']:.2f}")
        self.low_entry.delete(0, "end")
        self.low_entry.insert(0, str(d.get("low_threshold", 5)))

        self.history.config(state="normal")
        self.history.delete("1.0", "end")
        for entry in reversed(d.get("history", [])[-5:]):
            sign = "+" if entry["change"] >= 0 else ""
            line = f"{entry['date']} {sign}{entry['change']} → {entry['new_qty']}"
            if entry.get("note"):
                line += f" ({entry['note']})"
            self.history.insert("end", line + "\n")
        self.history.config(state="disabled")

    def clear_edit_fields(self):
        self.name_label.config(text="")
        self.qty_entry.delete(0, "end")
        self.price_entry.delete(0, "end")
        self.low_entry.delete(0, "end")
        self.note_entry.delete(0, "end")
        self.selected_item = None

    def change_qty(self, delta):
        if not self.selected_item:
            messagebox.showwarning("No selection", "Please select an item first.")
            return

        d = self.inventory[self.selected_item]
        new_qty = max(0, d["quantity"] + delta)
        change = new_qty - d["quantity"]
        d["quantity"] = new_qty

        note = self.note_entry.get().strip()
        self.add_history(self.selected_item, change, new_qty, note)

        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, str(new_qty))

        self.refresh_list()
        self.update_stats()
        self.on_item_select(None)

    def add_item(self):
        name = simpledialog.askstring("New Item", "Enter item name:")
        if not name or name.strip() == "" or name in self.inventory:
            return

        self.inventory[name.strip()] = {
            "quantity": 0,
            "price": 0.0,
            "low_threshold": 5,
            "history": []
        }
        self.add_history(name.strip(), 0, 0, "Item created")
        self.refresh_list()
        self.update_stats()

    def update_item(self):
        if not self.selected_item:
            messagebox.showwarning("Warning", "No item selected.")
            return

        try:
            qty = int(self.qty_entry.get())
            price = float(self.price_entry.get())
            low = int(self.low_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid number format.")
            return

        d = self.inventory[self.selected_item]
        change = qty - d["quantity"]

        d["quantity"] = qty
        d["price"] = price
        d["low_threshold"] = low

        if change != 0:
            note = self.note_entry.get().strip() or "Manual update"
            self.add_history(self.selected_item, change, qty, note)

        self.refresh_list()
        self.update_stats()
        self.on_item_select(None)

    def remove_item(self):
        if not self.selected_item:
            return

        item_name = self.selected_item
        if messagebox.askyesno("Confirm Delete", f"Delete {item_name}? (1 item)"):
            del self.inventory[item_name]
            self.selected_item = None
            self.refresh_list()
            self.update_stats()
            self.clear_edit_fields()

    def add_history(self, name, change, new_qty, note=""):
        if name not in self.inventory:
            return
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "change": change,
            "new_qty": new_qty,
            "note": note.strip()
        }
        self.inventory[name]["history"].append(entry)
        self.inventory[name]["history"] = self.inventory[name]["history"][-20:]

    def update_stats(self):
        total = sum(d["quantity"] * d["price"] for d in self.inventory.values())
        low_count = sum(1 for d in self.inventory.values() if d["quantity"] <= d.get("low_threshold", 5))
        self.stats_label.config(text=f"Total Value: ${total:,.2f}    Low Stock Items: {low_count}")

    def backup_inventory(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
        try:
            shutil.copy(INVENTORY_FILE, backup_path)
            messagebox.showinfo("Backup", f"Backup saved:\n{os.path.basename(backup_path)}")
        except Exception as e:
            messagebox.showerror("Backup Failed", str(e))

    def restore_inventory(self):
        file = filedialog.askopenfilename(initialdir=BACKUP_DIR, filetypes=[("JSON files", "*.json")])
        if file:
            try:
                shutil.copy(file, INVENTORY_FILE)
                self.inventory = self.load_inventory()
                self.refresh_list()
                self.update_stats()
                messagebox.showinfo("Restore", "Inventory restored successfully")
            except Exception as e:
                messagebox.showerror("Restore Failed", str(e))

    def generate_report(self):
        visible_only = messagebox.askyesno("Export Options",
                                           "Export only currently visible/filtered items?\n\n"
                                           "Yes = Filtered view\nNo = All items")

        file = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Inventory"
        )
        if not file:
            return

        try:
            with open(file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Qty", "Low Threshold", "Price", "Total"])

                items = self.get_visible_items() if visible_only else self.inventory.items()

                for name, d in sorted(items):
                    qty = d["quantity"]
                    price = d["price"]
                    writer.writerow([
                        name,
                        qty,
                        d.get("low_threshold", 5),
                        f"{price:.2f}",
                        f"{qty * price:.2f}"
                    ])
            messagebox.showinfo("Success", f"Exported to:\n{os.path.basename(file)}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def get_visible_items(self):
        """Return dict of currently visible items in the treeview"""
        visible = {}
        for iid in self.tree.get_children():
            name = iid
            if name in self.inventory:
                visible[name] = self.inventory[name]
        return visible.items()
    
    def print_table(self):
        # Simple HTML table for printing current visible items
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        html = f"""
        <html>
        <head><title>Inventory Print</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            h1 {{ text-align: center; }}
        </style>
        </head>
        <body>
        <h1>Inventory Report</h1>
        <p>Generated on: {now_str}</p>
        <table>
            <tr>
                <th>Item Name</th>
                <th>Qty</th>
                <th>Low @</th>
                <th>Price</th>
                <th>Total Value</th>
                <th>Status</th>
            </tr>
        """

        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            html += f"""
            <tr>
                <td>{values[0]}</td>
                <td>{values[1]}</td>
                <td>{values[2]}</td>
                <td>{values[3]}</td>
                <td>{values[4]}</td>
                <td>{values[5]}</td>
            </tr>
            """

        html += """
        </table>
        </body>
        </html>
        """

        with open("inventory_print.html", "w", encoding="utf-8") as f:
            f.write(html)

        webbrowser.open("inventory_print.html")

    def on_closing(self):
        if messagebox.askyesno("Quit", "Do you want to save changes before closing?"):
            try:
                with open(INVENTORY_FILE, 'w') as f:
                    json.dump(self.inventory, f, indent=4)
                print("Inventory saved automatically")
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not save inventory:\n{e}")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()
