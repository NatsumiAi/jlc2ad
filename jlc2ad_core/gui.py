import customtkinter as ctk
import threading

from .build import build_libraries


class JLC2AD_GUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LCSC to Altium Designer")
        self.geometry("700x550")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.create_widgets()

    def create_widgets(self):
        title_label = ctk.CTkLabel(
            self,
            text="LCSC 器件转 Altium Designer 元件库",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(20, 10))

        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(input_frame, text="LCSC 料号 (空格或换行分隔):").pack(anchor="w", padx=10, pady=(10, 5))
        self.part_input = ctk.CTkTextbox(input_frame, height=80)
        self.part_input.pack(fill="x", padx=10, pady=5)
        self.part_input.insert("1.0", "C15850\nC8291\nC9652")

        output_frame = ctk.CTkFrame(self)
        output_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(output_frame, text="输出文件名:").pack(anchor="w", padx=10, pady=(10, 5))
        self.output_input = ctk.CTkEntry(output_frame, placeholder_text="my_lib")
        self.output_input.pack(fill="x", padx=10, pady=5)
        self.output_input.insert(0, "my_lib")

        self.generate_btn = ctk.CTkButton(
            self,
            text="生成元件库",
            command=self.start_generation,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.generate_btn.pack(fill="x", padx=20, pady=10)

        self.progress = ctk.CTkProgressBar(self, width=500)
        self.progress.pack(pady=(0, 10))
        self.progress.set(0)

        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(log_frame, text="日志:").pack(anchor="w", padx=10, pady=(10, 5))
        self.log_text = ctk.CTkTextbox(log_frame, height=150)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text.configure(state="disabled")

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def start_generation(self):
        parts_text = self.part_input.get("1.0", "end").strip()
        if not parts_text:
            self.log("错误: 请输入 LCSC 料号")
            return

        parts = [p.strip() for p in parts_text.replace("\n", " ").split() if p.strip()]
        if not parts:
            self.log("错误: 请输入有效的 LCSC 料号")
            return

        output_name = self.output_input.get().strip()
        if not output_name:
            self.log("错误: 请输入输出文件名")
            return

        self.generate_btn.configure(state="disabled", text="生成中...")
        self.progress.set(0)

        thread = threading.Thread(target=self.generate, args=(parts, output_name))
        thread.start()

    def generate(self, parts, base):
        try:
            result = build_libraries(
                parts,
                base,
                log=self.log,
                progress=self.progress.set,
            )

            self.log(f"\n完成! 生成文件:")
            self.log(f"  {result.pcblib_path}")
            if result.symbols:
                self.log(f"  {result.schlib_path}")
            self.log(f"  {result.libpkg_path}")
            self.log(
                f"\n在 Altium Designer 中打开 {result.libpkg_path} -> Project -> Compile Integrated Library"
            )

            self.finish_generation(True)

        except Exception as e:
            if str(e) == "No components fetched":
                self.log("错误: 未获取到任何元件")
            else:
                self.log(f"错误: {e}")
            self.finish_generation(False)

    def finish_generation(self, success):
        self.generate_btn.configure(state="normal", text="生成元件库")
        if success:
            self.log("\n=== 生成成功 ===")
        else:
            self.log("\n=== 生成失败 ===")


def main():
    app = JLC2AD_GUI()
    app.mainloop()


if __name__ == '__main__':
    main()
