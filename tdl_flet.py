import flet as ft
import subprocess
import os
import threading
import re
import time
import signal
import locale
import sys
import psutil
from datetime import datetime

class TDLDownloaderApp:
    def __init__(self):
        # 获取系统默认编码
        self.system_encoding = locale.getpreferredencoding()
        
        # 初始化下载目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序
            base_path = os.path.dirname(sys.executable)
        else:
            # 如果是开发环境
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.downloads_dir = os.path.join(base_path, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        
        # 存储正在运行的进程
        self.running_processes = []
        
        # 环境变量
        self.env_vars = {
            "TDL_NS": "quickstart",
            "TDL_PROXY": "socks5://127.0.0.1:56789"
        }
        
        # 获取tdl.exe的完整路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序
            self.tdl_path = os.path.join(base_path, "tdl.exe")
        else:
            # 如果是开发环境
            self.tdl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdl.exe")

        # 初始化上传相关的变量
        self.upload_log_view = None
        self.upload_current_task_text = None
        self.upload_current_progress = None
        self.upload_current_progress_text = None
        self.upload_total_progress = None
        self.upload_total_progress_text = None
        self.selected_files = []
        
    def main(self, page: ft.Page):
        # 设置页面属性
        page.title = "TDL下载器"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.window_width = 1200
        page.window_height = 1300  # 根据元素总高度设置（约1285px，稍微取整）
        page.padding = 15
        page.scroll = None
        page.window_min_width = 1000
        page.window_min_height = 1200  # 设置最小高度
        
        # 设置主题颜色
        page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.BLUE,
            visual_density=ft.VisualDensity.COMFORTABLE,
        )

        # 定义文字样式
        title_style = ft.TextStyle(
            size=24,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE
        )
        
        subtitle_style = ft.TextStyle(
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE_900
        )
        
        normal_text_style = ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_400,
            color=ft.Colors.GREY_900
        )
        
        # 按钮样式
        button_style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.padding.all(15),
            color={
                "": ft.Colors.WHITE,
                "disabled": ft.Colors.GREY_700,
            },
            bgcolor={
                "": ft.Colors.BLUE,
                "hovered": ft.Colors.BLUE_700,
                "disabled": ft.Colors.GREY_400,
            },
            elevation={"pressed": 0, "": 2},
            animation_duration=200,
            side=ft.BorderSide(width=0),
        )
        
        text_button_style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.padding.all(8),
            color={
                "": ft.Colors.BLUE,
                "hovered": ft.Colors.BLUE_700,
            },
        )
        
        # 输入框样式
        textfield_style = {
            "expand": True,
            "border_radius": 8,
            "filled": True,
            "bgcolor": ft.Colors.BLUE_50,
            "border_color": ft.Colors.BLUE_200,
            "focused_border_color": ft.Colors.BLUE,
            "focused_bgcolor": ft.Colors.WHITE,
            "text_size": 14,
            "cursor_color": ft.Colors.BLUE,
            "selection_color": ft.Colors.BLUE_100,
        }

        # 创建下载标签页内容
        def create_download_tab():
            # 检查tdl.exe是否存在
            if not os.path.exists(self.tdl_path):
                page.dialog = ft.AlertDialog(
                    title=ft.Text("错误", size=18, weight=ft.FontWeight.BOLD),
                    content=ft.Text("未找到tdl.exe文件，请确保该程序与tdl.exe在同一目录下。", style=normal_text_style),
                    actions=[
                        ft.TextButton("确定", on_click=lambda e: self.close_dialog(e, False), style=text_button_style)
                    ]
                )
                page.dialog.open = True
                page.update()
            
            # 状态栏
            self.status_text = ft.Text("就绪", color=ft.Colors.BLUE, style=normal_text_style)
            
            # 环境变量设置
            ns_field = ft.TextField(
                label="命名空间 (TDL_NS)",
                value=self.env_vars["TDL_NS"],
                hint_text="输入命名空间",
                prefix_icon=ft.Icons.DNS_ROUNDED,
                **textfield_style
            )
            
            proxy_field = ft.TextField(
                label="代理 (TDL_PROXY)",
                value=self.env_vars["TDL_PROXY"],
                hint_text="输入代理地址",
                prefix_icon=ft.Icons.SECURITY_ROUNDED,
                **textfield_style
            )
            
            def set_namespace(e):
                ns = ns_field.value.strip()
                if not ns:
                    self.show_snackbar(page, "请输入命名空间")
                    return
                
                self.env_vars["TDL_NS"] = ns
                self.add_log(f"设置环境变量: TDL_NS={ns}")
                self.status_text.value = f"命名空间已设置为: {ns}"
                self.show_snackbar(page, f"命名空间已设置为: {ns}")
                page.update()
            
            def set_proxy(e):
                proxy = proxy_field.value.strip()
                if not proxy:
                    self.show_snackbar(page, "请输入代理地址")
                    return
                
                self.env_vars["TDL_PROXY"] = proxy
                self.add_log(f"设置环境变量: TDL_PROXY={proxy}")
                self.status_text.value = f"代理已设置为: {proxy}"
                self.show_snackbar(page, f"代理已设置为: {proxy}")
                page.update()
            
            # 下载链接输入
            links_field = ft.TextField(
                label="下载链接 (每行一个)",
                multiline=True,
                min_lines=6,
                max_lines=10,
                hint_text="在此粘贴下载链接，每行一个",
                prefix_icon=ft.Icons.LINK_ROUNDED,
                **textfield_style
            )
            
            # 进度条样式
            progress_style = {
                "bgcolor": ft.Colors.BLUE_50,
                "color": ft.Colors.BLUE,
            }
            
            # 进度条
            self.current_task_text = ft.Text("无任务", style=normal_text_style)
            
            self.current_progress = ft.ProgressBar(
                width=650,
                value=0,
                height=8,
                bar_height=8,
                tooltip="当前文件下载进度",
                **progress_style
            )
            self.current_progress_text = ft.Text("0%", style=normal_text_style)
            
            self.total_progress = ft.ProgressBar(
                width=650,
                value=0,
                height=10,
                bar_height=10,
                tooltip="总体下载进度",
                **progress_style
            )
            self.total_progress_text = ft.Text("0%", style=normal_text_style, weight=ft.FontWeight.BOLD)
            
            # 日志输出
            self.log_view = ft.ListView(
                expand=True,
                spacing=2,
                auto_scroll=True,
                height=450,  # 增加日志区域的高度
                padding=10
            )
            
            # 下载按钮
            download_button = ft.ElevatedButton(
                "开始下载",
                icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                style=button_style,
                on_click=self.start_download,
                expand=1
            )
            
            # 打开下载文件夹按钮
            open_folder_button = ft.ElevatedButton(
                "打开下载文件夹",
                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                style=button_style,
                on_click=self.open_download_folder,
                expand=1
            )
            
            # 清空日志按钮
            clear_log_button = ft.TextButton(
                "清空日志",
                icon=ft.Icons.CLEANING_SERVICES_ROUNDED,
                on_click=self.clear_logs,
                style=text_button_style
            )

            # 构建下载标签页布局
            return ft.Container(
                content=ft.Row(
                    [
                        # 左侧面板 - 环境设置和下载设置
                        ft.Container(
                            content=ft.Column(
                                [
                                    # 环境设置卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.SETTINGS_SUGGEST_ROUNDED, color=ft.Colors.ORANGE_400),
                                                        ft.Text("环境设置", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Row(
                                                    [
                                                        ns_field,
                                                        ft.ElevatedButton(
                                                            "设置",
                                                            icon=ft.Icons.SAVE_ROUNDED,
                                                            on_click=set_namespace,
                                                            style=button_style
                                                        )
                                                    ],
                                                    spacing=10
                                                ),
                                                ft.Row(
                                                    [
                                                        proxy_field,
                                                        ft.ElevatedButton(
                                                            "设置",
                                                            icon=ft.Icons.SAVE_ROUNDED,
                                                            on_click=set_proxy,
                                                            style=button_style
                                                        )
                                                    ],
                                                    spacing=10
                                                ),
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                    
                                    # 下载设置卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.LINK_ROUNDED, color=ft.Colors.GREEN_400),
                                                        ft.Text("下载设置", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                links_field,
                                                ft.Row(
                                                    [download_button, open_folder_button],
                                                    spacing=10
                                                ),
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=15),
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True
                            ),
                            expand=5,
                            padding=ft.padding.only(right=10)
                        ),
                        
                        # 右侧面板 - 下载进度和日志输出
                        ft.Container(
                            content=ft.Column(
                                [
                                    # 下载进度卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=ft.Colors.PURPLE_400),
                                                        ft.Text("下载进度", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Container(
                                                    content=ft.Column([
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.TASK_ALT_ROUNDED, color=ft.Colors.BLUE_400, size=16),
                                                            ft.Text("当前任务:", style=normal_text_style),
                                                            self.current_task_text
                                                        ]),
                                                        ft.Container(height=5),
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.FILE_DOWNLOAD_ROUNDED, color=ft.Colors.GREEN_400, size=16),
                                                            ft.Text("当前文件:", style=normal_text_style),
                                                            ft.Container(expand=True),
                                                            self.current_progress_text
                                                        ]),
                                                        self.current_progress,
                                                        ft.Container(height=10),
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=ft.Colors.ORANGE_400, size=16),
                                                            ft.Text("总体进度:", style=normal_text_style, weight=ft.FontWeight.BOLD),
                                                            ft.Container(expand=True),
                                                            self.total_progress_text
                                                        ]),
                                                        self.total_progress,
                                                    ]),
                                                    padding=ft.padding.only(top=10, bottom=10)
                                                ),
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                    
                                    # 输出日志卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.ARTICLE_ROUNDED, color=ft.Colors.CYAN_400),
                                                        ft.Text("输出日志", style=subtitle_style),
                                                        ft.Container(expand=True),
                                                        clear_log_button
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Container(
                                                    content=self.log_view,
                                                    border=ft.border.all(1, ft.Colors.BLUE_50),
                                                    border_radius=8,
                                                    bgcolor=ft.Colors.BLUE_50,
                                                    padding=10,
                                                    expand=True
                                                )
                                            ]),
                                            padding=15,
                                            expand=True
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=15),
                                        expand=True,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True
                            ),
                            expand=7,
                        ),
                    ],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                expand=True
            )

        # 创建上传标签页内容
        def create_upload_tab():
            # 上传文件选择
            self.selected_files = []
            
            # 创建一个Container来包装ListView，设置背景色和边框
            selected_files_text = ft.ListView(
                expand=False,
                height=120,  # 稍微减小文件列表的高度
                spacing=2,
                auto_scroll=True,
                controls=[
                    ft.Text(
                        "未选择文件",
                        style=normal_text_style,
                        size=14,
                        color=ft.Colors.GREY_700
                    )
                ]
            )
            
            selected_files_container = ft.Container(
                content=selected_files_text,
                bgcolor=ft.Colors.BLUE_50,
                border=ft.border.all(1, ft.Colors.BLUE_200),
                border_radius=8,
                padding=10,
                height=140  # 相应调整容器高度
            )

            def update_selected_files_text(files):
                selected_files_text.controls.clear()
                if not files:
                    selected_files_text.controls.append(
                        ft.Text(
                            "未选择文件",
                            style=normal_text_style,
                            size=14,
                            color=ft.Colors.GREY_700
                        )
                    )
                else:
                    for file in files:
                        selected_files_text.controls.append(
                            ft.Text(
                                f"• {file.name}",
                                style=normal_text_style,
                                size=14,
                                color=ft.Colors.GREY_700
                            )
                        )
                # 只有当ListView已经被添加到页面时才更新
                if selected_files_text.page:
                    selected_files_text.update()
            
            # 初始化显示"未选择文件"
            update_selected_files_text([])

            def pick_files_result(e: ft.FilePickerResultEvent):
                try:
                    if e.files:
                        self.selected_files = e.files
                        update_selected_files_text(e.files)
                        upload_button.disabled = False
                        upload_button.update()
                        self.add_upload_log(f"已选择 {len(e.files)} 个文件")
                except Exception as ex:
                    print(f"选择文件时出错: {str(ex)}")
            
            def pick_directory_result(e: ft.FilePickerResultEvent):
                try:
                    if e.path:
                        # 遍历目录下的所有文件
                        files = []
                        for root, _, filenames in os.walk(e.path):
                            for filename in sorted(filenames):  # 按文件名排序
                                file_path = os.path.join(root, filename)
                                # 创建一个类似FilePickerFile的对象
                                files.append(type('FileInfo', (), {
                                    'name': os.path.relpath(file_path, e.path),  # 显示相对路径
                                    'path': file_path
                                })())
                        
                        if files:
                            self.selected_files = files
                            # 显示文件列表，添加缩进以显示目录结构
                            selected_files_text.controls.clear()
                            for file in files:
                                parts = file.name.split(os.sep)
                                indent = "  " * (len(parts) - 1)
                                selected_files_text.controls.append(
                                    ft.Text(
                                        f"{indent}• {parts[-1]}",
                                        style=normal_text_style,
                                        size=14,
                                        color=ft.Colors.GREY_700
                                    )
                                )
                            selected_files_text.update()
                            upload_button.disabled = False
                            upload_button.update()
                            self.add_upload_log(f"已选择文件夹: {e.path}")
                            self.add_upload_log(f"共找到 {len(files)} 个文件")
                        else:
                            self.add_upload_log("所选文件夹为空")
                            self.show_snackbar(page, "所选文件夹为空")
                except Exception as ex:
                    print(f"选择文件夹时出错: {str(ex)}")
                    self.add_upload_log(f"选择文件夹时出错: {str(ex)}")
            
            # 创建文件选择器
            file_picker_single = ft.FilePicker(
                on_result=pick_files_result
            )
            file_picker_multiple = ft.FilePicker(
                on_result=pick_files_result
            )
            directory_picker = ft.FilePicker(
                on_result=pick_directory_result
            )
            
            # 添加到页面
            page.overlay.extend([file_picker_single, file_picker_multiple, directory_picker])
            
            # 调整文件选择卡片的间距
            file_picker_buttons = ft.Row(
                [
                    ft.ElevatedButton(
                        text="选择单个文件",
                        icon=ft.Icons.FILE_UPLOAD_ROUNDED,
                        style=button_style,
                        on_click=lambda _: file_picker_single.pick_files(
                            allow_multiple=False
                        )
                    ),
                    ft.ElevatedButton(
                        text="选择多个文件",
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        style=button_style,
                        on_click=lambda _: file_picker_multiple.pick_files(
                            allow_multiple=True
                        )
                    ),
                    ft.ElevatedButton(
                        text="选择文件夹",
                        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                        style=button_style,
                        on_click=lambda _: directory_picker.get_directory_path()
                    ),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,  # 居中对齐按钮组
            )

            # 上传配置
            chat_field = ft.TextField(
                label="目标聊天",
                hint_text="@用户名 或 聊天ID",
                prefix_icon=ft.Icons.CHAT_ROUNDED,
                **textfield_style
            )

            threads_field = ft.TextField(
                label="上传线程数",
                value="4",
                hint_text="每个任务的线程数",
                prefix_icon=ft.Icons.SETTINGS_ETHERNET_ROUNDED,
                **textfield_style
            )

            concurrent_field = ft.TextField(
                label="并发任务数",
                value="2",
                hint_text="同时上传的文件数",
                prefix_icon=ft.Icons.COMPARE_ARROWS_ROUNDED,
                **textfield_style
            )

            # 上传选项
            upload_as_photo = ft.Checkbox(
                label="以照片形式上传图片",
                value=False
            )

            delete_after_upload = ft.Checkbox(
                label="上传成功后删除本地文件",
                value=False
            )
            
            # 进度条样式
            progress_style = {
                "bgcolor": ft.Colors.BLUE_50,
                "color": ft.Colors.BLUE,
            }
            
            # 上传进度条
            self.upload_current_task_text = ft.Text("无任务", style=normal_text_style)
            
            self.upload_current_progress = ft.ProgressBar(
                width=650,
                value=0,
                height=8,
                bar_height=8,
                tooltip="当前文件上传进度",
                **progress_style
            )
            self.upload_current_progress_text = ft.Text("0%", style=normal_text_style)
            
            self.upload_total_progress = ft.ProgressBar(
                width=650,
                value=0,
                height=10,
                bar_height=10,
                tooltip="总体上传进度",
                **progress_style
            )
            self.upload_total_progress_text = ft.Text("0%", style=normal_text_style, weight=ft.FontWeight.BOLD)
            
            # 上传日志输出
            self.upload_log_view = ft.ListView(
                expand=True,
                spacing=2,
                auto_scroll=True,
                height=450,  # 增加日志区域的高度
                padding=10
            )
            
            def start_upload(e):
                try:
                    print("开始上传...")  # 调试输出
                    if not self.selected_files:
                        self.show_snackbar(page, "请先选择要上传的文件")
                        return
                    
                    # 获取配置
                    chat = chat_field.value.strip()
                    if not chat:
                        self.show_snackbar(page, "请输入目标聊天")
                        return

                    try:
                        threads = int(threads_field.value)
                        concurrent = int(concurrent_field.value)
                        if threads < 1 or concurrent < 1:
                            raise ValueError()
                    except:
                        self.show_snackbar(page, "线程数和并发数必须是大于0的整数")
                        return

                    # 禁用上传按钮
                    upload_button.disabled = True
                    upload_button.update()

                    # 添加初始日志
                    self.add_upload_log("开始上传任务...")
                    self.add_upload_log(f"目标聊天: {chat}")
                    self.add_upload_log(f"线程数: {threads}, 并发数: {concurrent}")
                    self.add_upload_log(f"以照片形式上传: {'是' if upload_as_photo.value else '否'}")
                    self.add_upload_log(f"上传后删除: {'是' if delete_after_upload.value else '否'}")

                    # 启动上传线程
                    threading.Thread(
                        target=self._upload_thread,
                        args=(
                            self.selected_files,
                            chat,
                            threads,
                            concurrent,
                            upload_as_photo.value,
                            delete_after_upload.value,
                            page
                        ),
                        daemon=True
                    ).start()
                    
                except Exception as ex:
                    print(f"启动上传任务时出错: {str(ex)}")  # 调试输出
                    self.add_upload_log(f"启动上传任务时出错: {str(ex)}")
                    self.show_snackbar(page, f"启动上传任务时出错: {str(ex)}")
                    upload_button.disabled = False
                    upload_button.update()
            
            # 创建上传按钮
            upload_button = ft.ElevatedButton(
                text="开始上传",
                icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                style=button_style,
                on_click=start_upload,
                disabled=True,
                expand=1
            )
            
            # 清空日志按钮
            clear_upload_log_button = ft.TextButton(
                text="清空日志",
                icon=ft.Icons.CLEANING_SERVICES_ROUNDED,
                on_click=lambda e: self.clear_upload_logs(),
                style=text_button_style
            )
            
            # 初始化上传日志
            self.add_upload_log("准备就绪，请选择要上传的文件")
            
            # 构建界面
            upload_tab = ft.Container(
                content=ft.Row(
                    [
                        # 左侧面板 - 上传设置
                        ft.Container(
                            content=ft.Column(
                                [
                                    # 文件选择卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.FOLDER_ROUNDED, color=ft.Colors.ORANGE_400),
                                                        ft.Text("文件选择", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                file_picker_buttons,
                                                ft.Container(height=10),
                                                ft.Text("已选择的文件:", style=normal_text_style),
                                selected_files_container,  # 使用container而不是直接使用ListView
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                    
                                    # 调整上传设置卡片的间距
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=ft.Colors.GREEN_400),
                                                        ft.Text("上传设置", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Container(height=5),  # 减小顶部间距
                                                ft.Row(
                                                    [chat_field],
                                                    spacing=10
                                                ),
                                                ft.Container(height=5),  # 减小间距
                                                ft.Row(
                                                    [threads_field, concurrent_field],
                                                    spacing=10
                                                ),
                                                ft.Container(height=5),  # 减小间距
                                                ft.Row(
                                                    [upload_as_photo, delete_after_upload],
                                                    spacing=10
                                                ),
                                                ft.Container(height=10),  # 减小间距
                                                upload_button,
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=15),
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True
                            ),
                            expand=5,
                            padding=ft.padding.only(right=10)
                        ),
                        
                        # 右侧面板 - 上传进度和日志输出
                        ft.Container(
                            content=ft.Column(
                                [
                                    # 上传进度卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=ft.Colors.PURPLE_400),
                                                        ft.Text("上传进度", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Container(
                                                    content=ft.Column([
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.TASK_ALT_ROUNDED, color=ft.Colors.BLUE_400, size=16),
                                                            ft.Text("当前任务:", style=normal_text_style),
                                                            self.upload_current_task_text
                                                        ]),
                                                        ft.Container(height=3),  # 减小间距
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.FILE_UPLOAD_ROUNDED, color=ft.Colors.GREEN_400, size=16),
                                                            ft.Text("当前文件:", style=normal_text_style),
                                                            ft.Container(expand=True),
                                                            self.upload_current_progress_text
                                                        ]),
                                                        self.upload_current_progress,
                                                        ft.Container(height=5),  # 减小间距
                                                        ft.Row([
                                                            ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=ft.Colors.ORANGE_400, size=16),
                                                            ft.Text("总体进度:", style=normal_text_style, weight=ft.FontWeight.BOLD),
                                                            ft.Container(expand=True),
                                                            self.upload_total_progress_text
                                                        ]),
                                                        self.upload_total_progress,
                                                    ]),
                                                    padding=ft.padding.only(top=10, bottom=10)
                                                ),
                                            ]),
                                            padding=15
                                        ),
                                        elevation=2,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                    
                                    # 上传日志卡片
                                    ft.Card(
                                        content=ft.Container(
                                            content=ft.Column([
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.ARTICLE_ROUNDED, color=ft.Colors.CYAN_400),
                                                        ft.Text("上传日志", style=subtitle_style),
                                                        ft.Container(expand=True),
                                                        clear_upload_log_button
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                ft.Container(
                                                    content=self.upload_log_view,
                                                    border=ft.border.all(1, ft.Colors.BLUE_50),
                                                    border_radius=8,
                                                    bgcolor=ft.Colors.BLUE_50,
                                                    padding=10,
                                                    expand=True
                                                )
                                            ]),
                                            padding=15,
                                            expand=True
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=15),
                                        expand=True,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True
                            ),
                            expand=7,
                        ),
                    ],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                expand=True
            )
            
            return upload_tab

        # 创建标签页
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="下载",
                    icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                    content=create_download_tab()
                ),
                ft.Tab(
                    text="上传",
                    icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                    content=create_upload_tab()
                ),
            ],
            expand=True
        )

        # 构建主界面
        page.add(
            ft.Container(
                content=ft.Column(
                    [
                        # 标题栏
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.CLOUD_SYNC_ROUNDED, size=28, color=ft.Colors.BLUE_500),
                                    ft.Text("TDL下载器", style=title_style),
                                    ft.Container(expand=True),
                                    self.status_text
                                ],
                                alignment=ft.MainAxisAlignment.START
                            ),
                            padding=ft.padding.only(bottom=15)
                        ),
                        # 标签页
                        tabs,
                    ],
                    expand=True
                ),
                expand=True
            )
        )
        
        # 添加系统编码信息
        self.add_log(f"系统编码: {self.system_encoding}")
        self.add_log(f"下载目录: {self.downloads_dir}")
        self.add_log("准备就绪，请输入下载链接并点击「开始下载」按钮")
    
    def show_snackbar(self, page, message):
        """显示提示消息"""
        snackbar_text_style = ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.WHITE
        )
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, style=snackbar_text_style),
            action="确定",
            action_color=ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_700,
            duration=3000
        )
        page.snack_bar.open = True
        page.update()
    
    def clear_logs(self, e):
        """清空日志"""
        self.log_view.controls.clear()
        self.add_log("日志已清空")
        self.add_log(f"系统编码: {self.system_encoding}")
        self.add_log(f"下载目录: {self.downloads_dir}")
        self.add_log("准备就绪，请输入下载链接并点击「开始下载」按钮")
    
    def add_log(self, text, replace_last=False):
        """添加日志
        Args:
            text: 日志文本
            replace_last: 是否替换最后一行日志
        """
        try:
            # 处理可能的乱码
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            elif isinstance(text, str):
                # 尝试重新编码解码来处理潜在的乱码
                text = text.encode('utf-8', errors='replace').decode('utf-8')
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_text_style = ft.TextStyle(
                size=13,
                weight=ft.FontWeight.W_400,
                color=ft.Colors.GREY_800,
                font_family="Consolas"  # 使用等宽字体
            )
            
            # 如果需要替换最后一行
            if replace_last and len(self.log_view.controls) > 0:
                self.log_view.controls[-1].content.value = f"[{timestamp}] {text}"
                self.log_view.controls[-1].content.update()
            else:
                self.log_view.controls.append(
                    ft.Container(
                        content=ft.Text(f"[{timestamp}] {text}", selectable=True, style=log_text_style),
                        padding=ft.padding.symmetric(vertical=2)
                    )
                )
                
            if len(self.log_view.controls) > 1000:  # 限制日志数量
                self.log_view.controls.pop(0)
            
            # 检查log_view是否已添加到页面
            try:
                self.log_view.update()
            except:
                # 如果未添加到页面，忽略更新错误
                pass
        except Exception as e:
            print(f"添加日志时出错: {str(e)}")

    def update_progress(self, current_value=None, total_value=None, text=None):
        """更新进度条"""
        try:
            if current_value is not None:
                # 确保进度值在有效范围内
                current_value = max(0, min(100, current_value))
                # 使用极小的阈值，几乎实时更新
                if abs(self.current_progress.value * 100 - current_value) >= 0.01:
                    self.current_progress.value = current_value / 100
                    # 只在整数值变化时更新文本
                    new_text = f"{int(current_value)}%"
                    if self.current_progress_text.value != new_text:
                        self.current_progress_text.value = new_text
                        self.current_progress_text.update()
                    self.current_progress.update()
            
            if total_value is not None:
                # 确保进度值在有效范围内
                total_value = max(0, min(100, total_value))
                # 使用极小的阈值，几乎实时更新
                if abs(self.total_progress.value * 100 - total_value) >= 0.01:
                    self.total_progress.value = total_value / 100
                    # 只在整数值变化时更新文本
                    new_text = f"{int(total_value)}%"
                    if self.total_progress_text.value != new_text:
                        self.total_progress_text.value = new_text
                        self.total_progress_text.update()
                    self.total_progress.update()
            
            if text and self.current_task_text.value != text:
                self.current_task_text.value = text
                self.current_task_text.update()

        except Exception as e:
            print(f"更新进度条时出错: {str(e)}")
    
    def open_download_folder(self, e=None):
        """打开下载文件夹"""
        try:
            self.add_log(f"打开下载文件夹: {self.downloads_dir}")
            if os.path.exists(self.downloads_dir):
                if os.name == 'nt':  # Windows
                    os.startfile(self.downloads_dir)
                elif os.name == 'posix':  # Linux, macOS
                    try:
                        subprocess.Popen(['xdg-open', self.downloads_dir])  # Linux
                    except:
                        subprocess.Popen(['open', self.downloads_dir])  # macOS
            else:
                self.add_log("下载文件夹不存在，正在创建...")
                os.makedirs(self.downloads_dir, exist_ok=True)
                self.open_download_folder()
        except Exception as e:
            self.add_log(f"打开下载文件夹时出错: {str(e)}")
    
    def start_download(self, e):
        """开始下载"""
        try:
            # 获取下载链接
            # 在新的左右布局中，找到链接输入框
            links_field = None
            # 遍历页面寻找链接输入框
            for control in e.page.controls:
                if isinstance(control, ft.Container):
                    tabs = control.content.controls[1]  # 获取标签页控件
                    if isinstance(tabs, ft.Tabs):
                        download_tab = tabs.tabs[0].content  # 获取下载标签页内容
                        left_panel = download_tab.content.controls[0]  # 获取左侧面板
                        download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                        links_field = download_card.content.content.controls[2]  # 获取链接输入框
                        break
            
            if not links_field:
                raise Exception("无法找到链接输入框")
            
            links_text = links_field.value.strip()
            if not links_text:
                self.show_snackbar(e.page, "请输入下载链接")
                return
            
            # 分割多行链接
            links = [link.strip() for link in links_text.split("\n") if link.strip()]
            
            # 禁用按钮
            download_button = None
            for control in e.page.controls:
                if isinstance(control, ft.Container):
                    tabs = control.content.controls[1]  # 获取标签页控件
                    if isinstance(tabs, ft.Tabs):
                        download_tab = tabs.tabs[0].content  # 获取下载标签页内容
                        left_panel = download_tab.content.controls[0]  # 获取左侧面板
                        download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                        download_button = download_card.content.content.controls[3].controls[0]  # 获取下载按钮
                        break
            
            if download_button:
                download_button.disabled = True
                download_button.update()
            
            # 确保下载目录存在
            os.makedirs(self.downloads_dir, exist_ok=True)
            
            # 启动下载线程
            threading.Thread(target=self._download_thread, args=(links, e.page), daemon=True).start()
        
        except Exception as ex:
            self.add_log(f"启动下载时出错: {str(ex)}")
            self.show_snackbar(e.page, f"启动下载时出错: {str(ex)}")
    
    def _download_thread(self, links, page):
        try:
            self.status_text.value = "正在下载..."
            self.status_text.color = ft.Colors.ORANGE
            self.status_text.update()
            self.add_log(f"下载保存目录: {self.downloads_dir}")
            
            # 重置进度条
            self.update_progress(current_value=0, total_value=0, text="准备下载")
            
            # 创建批处理文件内容
            batch_content = "@echo off\n"
            batch_content += "chcp 65001\n"  # 设置CMD编码为UTF-8
            batch_content += "set PYTHONIOENCODING=utf-8\n"  # 设置Python输出编码
            
            # 添加环境变量设置命令
            for var_name, var_value in self.env_vars.items():
                batch_content += f"set {var_name}={var_value}\n"
            
            # 添加下载命令
            total_links = len(links)
            for i, link in enumerate(links):
                # 添加下载命令到批处理文件
                dl_cmd = f"tdl.exe dl -u {link}"
                batch_content += f"echo [TDLGUI_MARKER] 开始下载 {i+1}/{total_links}: {link}\n"
                batch_content += f"{dl_cmd}\n"
                batch_content += f"echo [TDLGUI_MARKER] 完成下载 {i+1}/{total_links}\n"
                self.add_log(f"添加下载命令: {dl_cmd}")
            
            # 创建临时批处理文件
            batch_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdl_download.bat")
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write(batch_content)
            
            self.add_log(f"已创建批处理文件: {batch_file}")
            
            # 执行批处理文件
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(
                batch_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                startupinfo=startupinfo,
                env=dict(os.environ, PYTHONIOENCODING='utf-8')  # 设置Python输出编码
            )
            
            # 将进程添加到列表中
            self.running_processes.append(process)
            
            # 在进度解析部分进行优化
            current_file_index = 0
            completed_files = 0
            is_downloading = False
            last_progress = 0
            current_progress_line = None  # 当前进度输出行
            progress_bar_width = 30  # 进度条宽度
            
            def make_progress_bar(progress):
                """生成文本进度条"""
                filled = int(progress_bar_width * progress / 100)
                bar = '█' * filled + '░' * (progress_bar_width - filled)
                return f"[{bar}] {progress:.1f}%"
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    try:
                        # 处理编码问题
                        if isinstance(line, bytes):
                            line = line.decode('utf-8', errors='replace')
                        line = line.strip()
                        
                        # 检测我们的特殊标记
                        if "[TDLGUI_MARKER] 开始下载" in line:
                            match = re.search(r'开始下载 (\d+)/(\d+): (.+)$', line)
                            if match:
                                current_file_index = int(match.group(1)) - 1
                                file_url = match.group(3)
                                is_downloading = True
                                current_progress_line = f"正在下载 ({current_file_index+1}/{total_links}): {file_url}\n{make_progress_bar(0)}"
                                self.add_log(current_progress_line)
                                self.update_progress(
                                    current_value=0,
                                    text=f"下载文件 {current_file_index+1}/{total_links}"
                                )
                                total_progress = (completed_files / total_links) * 100
                                self.update_progress(total_value=total_progress)
                                last_progress = 0
                        
                        elif "[TDLGUI_MARKER] 完成下载" in line:
                            completed_files += 1
                            is_downloading = False
                            if current_progress_line:
                                final_progress = f"正在下载 ({current_file_index+1}/{total_links}): {file_url}\n{make_progress_bar(100)} - 完成"
                                self.add_log(final_progress, replace_last=True)
                                current_progress_line = None
                            self.update_progress(current_value=100)
                            total_progress = (completed_files / total_links) * 100
                            self.update_progress(total_value=total_progress)
                            last_progress = 100
                        
                        # 如果正在下载，尝试从输出中解析进度
                        elif is_downloading:
                            progress_match = re.search(r'(\d+\.\d+)%', line)
                            if progress_match and current_progress_line:
                                file_progress = float(progress_match.group(1))
                                # 更新进度条
                                progress_text = f"正在下载 ({current_file_index+1}/{total_links}): {file_url}\n{make_progress_bar(file_progress)}"
                                self.add_log(progress_text, replace_last=True)
                                # 更新进度条
                                self.update_progress(current_value=file_progress)
                                total_progress = ((completed_files + file_progress / 100) / total_links) * 100
                                self.update_progress(total_value=total_progress)
                                last_progress = file_progress
                            elif not progress_match and not line.startswith("[TDLGUI_MARKER]"):
                                # 输出非进度信息
                                self.add_log(line)
                    
                    except Exception as e:
                        self.add_log(f"[日志解析错误: {str(e)}]")
            
            # 删除临时批处理文件
            try:
                os.remove(batch_file)
                self.add_log("已删除临时批处理文件")
            except:
                self.add_log("无法删除临时批处理文件")
            
            return_code = process.poll()
            if return_code == 0:
                self.add_log("所有链接下载成功!")
                self.show_snackbar(page, "下载完成！")
            else:
                self.add_log(f"下载过程中出现错误，返回码: {return_code}")
                self.show_snackbar(page, f"下载出现错误，返回码: {return_code}")
            
            # 从列表中移除已完成的进程
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            # 完成所有下载
            self.update_progress(current_value=100, total_value=100, text="下载完成")
            self.status_text.value = "下载完成"
            self.status_text.color = ft.Colors.GREEN
            self.status_text.update()
            self.add_log("所有下载任务已完成")
            self.add_log(f"下载文件保存在: {self.downloads_dir}")
            self.add_log("您可以点击「打开下载文件夹」按钮查看下载的文件")
                
        except Exception as e:
            self.status_text.value = f"错误: {str(e)}"
            self.status_text.color = ft.Colors.RED
            self.status_text.update()
            self.add_log(f"发生错误: {str(e)}")
            self.show_snackbar(page, f"发生错误: {str(e)}")
        finally:
            try:
                # 尝试在标签页内容中查找下载按钮
                download_button = None
                for control in page.controls:
                    if isinstance(control, ft.Container):
                        tabs = control.content.controls[1]  # 获取标签页控件
                        if isinstance(tabs, ft.Tabs):
                            download_tab = tabs.tabs[0].content  # 获取下载标签页内容
                            left_panel = download_tab.content.controls[0]  # 获取左侧面板
                            download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                            download_button = download_card.content.content.controls[3].controls[0]  # 获取下载按钮
                            break
                
                if download_button:
                    download_button.disabled = False
                    download_button.update()
                else:
                    print("无法找到下载按钮")
            except Exception as e:
                print(f"重新启用下载按钮时出错: {str(e)}")

    def _upload_thread(self, files, chat, threads, concurrent, as_photo, delete_after, page):
        try:
            self.status_text.value = "正在上传..."
            self.status_text.color = ft.Colors.ORANGE
            self.status_text.update()
            
            # 重置进度条
            self.update_upload_progress(current_value=0, total_value=0, text="准备上传")
            
            # 创建批处理文件内容
            batch_content = "@echo off\n"
            batch_content += "chcp 65001\n"  # 设置CMD编码为UTF-8
            batch_content += "set PYTHONIOENCODING=utf-8\n"  # 设置Python输出编码
            
            # 添加环境变量设置命令
            for var_name, var_value in self.env_vars.items():
                batch_content += f"set {var_name}={var_value}\n"
            
            # 添加上传命令
            total_files = len(files)
            for i, file in enumerate(files):
                # 构建上传命令
                up_cmd = f"tdl.exe up -p \"{file.path}\" -c {chat} -t {threads} -l {concurrent}"
                if as_photo:
                    up_cmd += " --photo"
                if delete_after:
                    up_cmd += " --rm"
                
                batch_content += f"echo [TDLGUI_MARKER] 开始上传 {i+1}/{total_files}: {file.name}\n"
                batch_content += f"{up_cmd}\n"
                batch_content += f"echo [TDLGUI_MARKER] 完成上传 {i+1}/{total_files}\n"
                self.add_upload_log(f"添加上传命令: {up_cmd}")
            
            # 创建临时批处理文件
            batch_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdl_upload.bat")
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write(batch_content)
            
            self.add_upload_log(f"已创建批处理文件: {batch_file}")
            
            # 执行批处理文件
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(
                batch_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                startupinfo=startupinfo,
                env=dict(os.environ, PYTHONIOENCODING='utf-8')  # 设置Python输出编码
            )
            
            # 将进程添加到列表中
            self.running_processes.append(process)
            
            # 在进度解析部分进行优化
            current_file_index = 0
            completed_files = 0
            is_uploading = False
            last_progress = 0
            current_progress_line = None  # 当前进度输出行
            progress_bar_width = 30  # 进度条宽度
            
            def make_progress_bar(progress):
                """生成文本进度条"""
                filled = int(progress_bar_width * progress / 100)
                bar = '█' * filled + '░' * (progress_bar_width - filled)
                return f"[{bar}] {progress:.1f}%"
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    try:
                        # 处理编码问题
                        if isinstance(line, bytes):
                            line = line.decode('utf-8', errors='replace')
                        line = line.strip()
                        
                        # 检测我们的特殊标记
                        if "[TDLGUI_MARKER] 开始上传" in line:
                            match = re.search(r'开始上传 (\d+)/(\d+): (.+)$', line)
                            if match:
                                current_file_index = int(match.group(1)) - 1
                                file_name = match.group(3)
                                is_uploading = True
                                current_progress_line = f"正在上传 ({current_file_index+1}/{total_files}): {file_name}\n{make_progress_bar(0)}"
                                self.add_upload_log(current_progress_line)
                                self.update_upload_progress(
                                    current_value=0,
                                    text=f"上传文件 {current_file_index+1}/{total_files}"
                                )
                                total_progress = (completed_files / total_files) * 100
                                self.update_upload_progress(total_value=total_progress)
                                last_progress = 0
                        
                        elif "[TDLGUI_MARKER] 完成上传" in line:
                            completed_files += 1
                            is_uploading = False
                            if current_progress_line:
                                final_progress = f"正在上传 ({current_file_index+1}/{total_files}): {file_name}\n{make_progress_bar(100)} - 完成"
                                self.add_upload_log(final_progress, replace_last=True)
                                current_progress_line = None
                            self.update_upload_progress(current_value=100)
                            total_progress = (completed_files / total_files) * 100
                            self.update_upload_progress(total_value=total_progress)
                            last_progress = 100
                        
                        # 如果正在上传，尝试从输出中解析进度
                        elif is_uploading:
                            progress_match = re.search(r'(\d+\.\d+)%', line)
                            if progress_match and current_progress_line:
                                file_progress = float(progress_match.group(1))
                                # 更新进度条
                                progress_text = f"正在上传 ({current_file_index+1}/{total_files}): {file_name}\n{make_progress_bar(file_progress)}"
                                self.add_upload_log(progress_text, replace_last=True)
                                # 更新进度条
                                self.update_upload_progress(current_value=file_progress)
                                total_progress = ((completed_files + file_progress / 100) / total_files) * 100
                                self.update_upload_progress(total_value=total_progress)
                                last_progress = file_progress
                            elif not progress_match and not line.startswith("[TDLGUI_MARKER]"):
                                # 输出非进度信息
                                self.add_upload_log(line)
                    
                    except Exception as e:
                        self.add_upload_log(f"[日志解析错误: {str(e)}]")
            
            # 删除临时批处理文件
            try:
                os.remove(batch_file)
                self.add_upload_log("已删除临时批处理文件")
            except:
                self.add_upload_log("无法删除临时批处理文件")
            
            return_code = process.poll()
            if return_code == 0:
                self.add_upload_log("所有文件上传成功!")
                self.show_snackbar(page, "上传完成！")
            else:
                self.add_upload_log(f"上传过程中出现错误，返回码: {return_code}")
                self.show_snackbar(page, f"上传出现错误，返回码: {return_code}")
            
            # 从列表中移除已完成的进程
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            # 完成所有上传
            self.update_upload_progress(current_value=100, total_value=100, text="上传完成")
            self.status_text.value = "上传完成"
            self.status_text.color = ft.Colors.GREEN
            self.status_text.update()
            self.add_upload_log("所有上传任务已完成")
                
        except Exception as e:
            self.status_text.value = f"错误: {str(e)}"
            self.status_text.color = ft.Colors.RED
            self.status_text.update()
            self.add_upload_log(f"发生错误: {str(e)}")
            self.show_snackbar(page, f"发生错误: {str(e)}")
        finally:
            try:
                # 尝试在标签页内容中查找上传按钮
                tabs = page.controls[0].content.controls[1]  # 获取标签页控件
                upload_tab = tabs.tabs[1].content  # 获取上传标签页内容
                upload_settings_card = upload_tab.content.controls[0].content.controls[1]  # 获取上传设置卡片
                upload_button = upload_settings_card.content.content.controls[-1]  # 获取上传按钮
                
                # 重新启用按钮
                upload_button.disabled = False
                upload_button.update()
            except Exception as e:
                print(f"重新启用上传按钮时出错: {str(e)}")

    def clear_upload_logs(self):
        """清空上传日志"""
        if self.upload_log_view is not None:
            self.upload_log_view.controls.clear()
            self.add_upload_log("上传日志已清空")
            self.add_upload_log("准备就绪，请选择要上传的文件")

    def add_upload_log(self, text, replace_last=False):
        """添加上传日志
        Args:
            text: 日志文本
            replace_last: 是否替换最后一行日志
        """
        try:
            if self.upload_log_view is None:
                print(f"Upload log: {text}")  # 如果日志视图未初始化，打印到控制台
                return

            # 处理可能的乱码
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            elif isinstance(text, str):
                # 尝试重新编码解码来处理潜在的乱码
                text = text.encode('utf-8', errors='replace').decode('utf-8')
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_text_style = ft.TextStyle(
                size=13,
                weight=ft.FontWeight.W_400,
                color=ft.Colors.GREY_800,
                font_family="Consolas"  # 使用等宽字体
            )
            
            # 如果需要替换最后一行
            if replace_last and len(self.upload_log_view.controls) > 0:
                self.upload_log_view.controls[-1].content.value = f"[{timestamp}] {text}"
                self.upload_log_view.controls[-1].content.update()
            else:
                self.upload_log_view.controls.append(
                    ft.Container(
                        content=ft.Text(f"[{timestamp}] {text}", selectable=True, style=log_text_style),
                        padding=ft.padding.symmetric(vertical=2)
                    )
                )
                
            if len(self.upload_log_view.controls) > 1000:  # 限制日志数量
                self.upload_log_view.controls.pop(0)
            
            # 检查log_view是否已添加到页面
            try:
                self.upload_log_view.update()
            except:
                # 如果未添加到页面，忽略更新错误
                pass
        except Exception as e:
            print(f"添加上传日志时出错: {str(e)}")

    def update_upload_progress(self, current_value=None, total_value=None, text=None):
        """更新上传进度条"""
        try:
            if current_value is not None and self.upload_current_progress is not None:
                # 确保进度值在有效范围内
                current_value = max(0, min(100, current_value))
                # 使用极小的阈值，几乎实时更新
                if abs(self.upload_current_progress.value * 100 - current_value) >= 0.01:
                    self.upload_current_progress.value = current_value / 100
                    # 只在整数值变化时更新文本
                    new_text = f"{int(current_value)}%"
                    if self.upload_current_progress_text.value != new_text:
                        self.upload_current_progress_text.value = new_text
                        self.upload_current_progress_text.update()
                    self.upload_current_progress.update()
            
            if total_value is not None and self.upload_total_progress is not None:
                # 确保进度值在有效范围内
                total_value = max(0, min(100, total_value))
                # 使用极小的阈值，几乎实时更新
                if abs(self.upload_total_progress.value * 100 - total_value) >= 0.01:
                    self.upload_total_progress.value = total_value / 100
                    # 只在整数值变化时更新文本
                    new_text = f"{int(total_value)}%"
                    if self.upload_total_progress_text.value != new_text:
                        self.upload_total_progress_text.value = new_text
                        self.upload_total_progress_text.update()
                    self.upload_total_progress.update()
            
            if text is not None and self.upload_current_task_text is not None:
                if self.upload_current_task_text.value != text:
                    self.upload_current_task_text.value = text
                    self.upload_current_task_text.update()

        except Exception as e:
            print(f"更新上传进度条时出错: {str(e)}")
    
    def kill_tdl_processes(self):
        """终止所有tdl进程"""
        # 先尝试终止我们启动的进程
        for process in self.running_processes:
            try:
                process.terminate()
                self.add_log("已终止tdl进程")
            except:
                pass
        
        # 然后查找并终止所有tdl进程
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'tdl' in proc.info['name'].lower():
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        self.add_log(f"已终止tdl进程 (PID: {proc.info['pid']})")
                    except:
                        pass
        except:
            # 如果psutil不可用，使用taskkill命令(Windows)
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'tdl.exe'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.add_log("已使用taskkill终止所有tdl进程")
            except:
                self.add_log("无法终止tdl进程")
    
    def on_closing(self, e):
        """关闭窗口时的处理"""
        e.page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认退出", size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text("确定要退出程序吗？\n所有正在进行的下载将被中断。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self.close_dialog(e, False)),
                ft.ElevatedButton("确定", on_click=lambda e: self.close_dialog(e, True))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        e.page.dialog.open = True
        e.page.update()
        return False  # 阻止窗口关闭，等待对话框确认
    
    def close_dialog(self, e, confirmed):
        """处理关闭对话框结果"""
        e.page.dialog.open = False
        e.page.update()
        
        if confirmed:
            # 终止所有tdl进程
            self.kill_tdl_processes()
            # 关闭应用
            e.page.window_destroy()

if __name__ == "__main__":
    app = TDLDownloaderApp()
    ft.app(target=app.main) 