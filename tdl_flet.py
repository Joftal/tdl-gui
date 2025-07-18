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
        
        # 初始化网络速度显示相关的属性
        self.download_speed_text = ft.Text("0 B/s", style=ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_400,
            color=ft.Colors.GREEN_400
        ))
        self.upload_speed_text = ft.Text("0 B/s", style=ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_400,
            color=ft.Colors.GREEN_400
        ))
        self.current_download_speed = "0 B/s"
        self.current_upload_speed = "0 B/s"
        
        # 初始化下载目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序，使用程序所在目录
            base_path = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # 如果是开发环境，使用脚本所在目录
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # 保存基础路径
        self.base_path = base_path
        
        self.downloads_dir = os.path.join(base_path, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        
        # 存储正在运行的进程
        self.running_processes = []
        
        # 存储下载链接和文件名的映射关系
        self.download_links_map = {}
        
        # 环境变量
        self.env_vars = {
            "TDL_NS": "quickstart",
            "TDL_PROXY": "socks5://127.0.0.1:56789"
        }
        
        # 获取tdl.exe的完整路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序，使用程序所在目录
            self.tdl_path = os.path.join(base_path, "tdl.exe")
        else:
            # 如果是开发环境，使用脚本所在目录
            self.tdl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdl.exe")

        # 初始化上传相关的变量
        self.upload_log_view = None
        self.upload_current_task_text = None
        self.upload_current_progress = None
        self.upload_current_progress_text = None
        self.upload_total_progress = None
        self.upload_total_progress_text = None
        self.selected_files = []
        
        # 初始化多任务下载设置
        self.enable_multi_task = False
        
        # 初始化下载进度显示
        self.download_speed_text = ft.Text("0 B/s", style=ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_400,
            color=ft.Colors.GREEN_400
        ))
        self.current_download_speed = "0 B/s"
        
        # 初始化总体进度条
        self.total_progress_bar = ft.ProgressBar(
            width=600,
            value=0,
            height=10,  # 增加高度使进度条更明显
            bar_height=10,
            bgcolor=ft.Colors.BLUE_50,
            color=ft.Colors.BLUE,
        )
        self.total_progress_text = ft.Text(
            "0%",
            style=ft.TextStyle(
                size=14,
                weight=ft.FontWeight.BOLD,  # 加粗显示进度
                color=ft.Colors.BLUE_700
            )
        )
        
        # 初始化任务进度
        self.total_tasks = 0
        self.completed_tasks = 0
        self.current_task_progress = 0

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

        # 创建状态文本控件
        # 将状态文本添加到页面
        # page.add(self.status_text) # This line is removed

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
            
            # 创建任务列表容器
            self.tasks_container = ft.Container(
                content=ft.Column([], spacing=10),
                bgcolor=ft.Colors.BLUE_50,
                border_radius=8,
                padding=10,
                expand=True,
                height=300,  # 增加高度以显示更多任务
                border=ft.border.all(1, ft.Colors.BLUE_200),
            )
            
            # 状态栏
            # self.status_text.value = "就绪" # This line is removed
            # self.status_text.color = ft.Colors.BLUE # This line is removed
            # self.status_text.update() # This line is removed
            
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
                # self.status_text.value = f"命名空间已设置为: {ns}" # This line is removed
                self.show_snackbar(page, f"命名空间已设置为: {ns}")
                page.update()
            
            def set_proxy(e):
                proxy = proxy_field.value.strip()
                if not proxy:
                    self.show_snackbar(page, "请输入代理地址")
                    return
                
                self.env_vars["TDL_PROXY"] = proxy
                self.add_log(f"设置环境变量: TDL_PROXY={proxy}")
                # self.status_text.value = f"代理已设置为: {proxy}" # This line is removed
                self.show_snackbar(page, f"代理已设置为: {proxy}")
                page.update()
            
            # 下载链接输入
            links_field = ft.TextField(
                label="下载链接 (每行一个)",
                multiline=True,
                min_lines=10,
                max_lines=10,  # 减少显示行数
                height=220,   # 减少固定高度
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
                                                ft.Container(
                                                    content=links_field,
                                                    height=220,  # 减少容器高度
                                                ),
                                                # 添加多任务下载开关
                                                ft.Row(
                                                    [
                                                        ft.Checkbox(
                                                            label="启用多任务下载",
                                                            value=False,
                                                            on_change=lambda e: toggle_multi_task(e),
                                                        ),
                                                    ],
                                                    spacing=10
                                                ),
                                                # 多任务设置（默认隐藏）
                                                ft.Container(
                                                    content=ft.Row(
                                                        [
                                                            ft.TextField(
                                                                label="下载线程数",
                                                                value="4",
                                                                hint_text="每个任务的线程数",
                                                                prefix_icon=ft.Icons.SETTINGS_ETHERNET_ROUNDED,
                                                                expand=True,
                                                                border_radius=8,
                                                                filled=True,
                                                                bgcolor=ft.Colors.BLUE_50,
                                                                border_color=ft.Colors.BLUE_200,
                                                                focused_border_color=ft.Colors.BLUE,
                                                                focused_bgcolor=ft.Colors.WHITE,
                                                                text_size=14,
                                                                cursor_color=ft.Colors.BLUE,
                                                                selection_color=ft.Colors.BLUE_100,
                                                                disabled=True,
                                                            ),
                                                            ft.TextField(
                                                                label="并发任务数",
                                                                value="2",
                                                                hint_text="同时下载的文件数",
                                                                prefix_icon=ft.Icons.COMPARE_ARROWS_ROUNDED,
                                                                expand=True,
                                                                border_radius=8,
                                                                filled=True,
                                                                bgcolor=ft.Colors.BLUE_50,
                                                                border_color=ft.Colors.BLUE_200,
                                                                focused_border_color=ft.Colors.BLUE,
                                                                focused_bgcolor=ft.Colors.WHITE,
                                                                text_size=14,
                                                                cursor_color=ft.Colors.BLUE,
                                                                selection_color=ft.Colors.BLUE_100,
                                                                disabled=True,
                                                            ),
                                                        ],
                                                        spacing=10
                                                    ),
                                                    visible=False,
                                                ),
                                                ft.Row(
                                                    [download_button, open_folder_button],
                                                    spacing=10
                                                ),
                                            ]),
                                            padding=5
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=15),
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True,
                                scroll='auto',  # 让左侧内容整体可滚动
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
                                                # 标题行
                                                ft.Row(
                                                    [
                                                        ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=ft.Colors.BLUE_400),
                                                        ft.Text("下载状态", style=subtitle_style),
                                                    ]
                                                ),
                                                ft.Divider(height=1, thickness=1, color=ft.Colors.BLACK12),
                                                # 速度和进度行
                                                ft.Container(
                                                    content=ft.Column([
                                                        ft.Row(
                                                            [
                                                                ft.Row(
                                                                    [
                                                                        ft.Text(
                                                                            "下载速度：",
                                                                            style=ft.TextStyle(
                                                                                size=14,
                                                                                weight=ft.FontWeight.W_500,
                                                                                color=ft.Colors.GREY_800
                                                                            ),
                                                                        ),
                                                                        ft.Icon(ft.Icons.SPEED_ROUNDED, 
                                                                               color=ft.Colors.GREEN_400,
                                                                               size=16),
                                                                        self.download_speed_text,
                                                                    ],
                                                                ),
                                                                ft.Container(expand=True),
                                                                ft.Row(
                                                                    [
                                                                        ft.Text(
                                                                            "下载进度：",
                                                                            style=ft.TextStyle(
                                                                                size=14,
                                                                                weight=ft.FontWeight.W_500,
                                                                                color=ft.Colors.GREY_800
                                                                            ),
                                                                        ),
                                                                        self.total_progress_text,
                                                                    ],
                                                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                                ),
                                                            ],
                                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                        ),
                                                        ft.Container(height=10),  # 增加间距
                                                        self.total_progress_bar,
                                                    ]),
                                                    padding=10
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
                                                        ft.IconButton(
                                                            icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                                            tooltip="复制全部日志",
                                                            on_click=lambda e: self._copy_logs_to_clipboard(e, page),
                                                            style=ft.ButtonStyle(
                                                                shape=ft.RoundedRectangleBorder(radius=6),
                                                                padding=ft.padding.all(8),
                                                                bgcolor=ft.Colors.BLUE_100,
                                                                color=ft.Colors.BLUE_700,
                                                            ),
                                                        ),
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
                                                    expand=True,
                                                    height=400  # 调整日志区域高度
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

        def toggle_multi_task(e):
            """切换多任务下载状态"""
            self.enable_multi_task = e.control.value
            # 获取多任务设置容器
            multi_task_container = None
            thread_field = None
            concurrent_field = None
            
            for control in page.controls:
                if isinstance(control, ft.Container):
                    content_column = control.content
                    if isinstance(content_column, ft.Column):
                        main_content = content_column.controls[1]
                        if isinstance(main_content, ft.Container):
                            stack = main_content.content.content
                            if isinstance(stack, ft.Stack):
                                download_tab = stack.controls[0]
                                if download_tab.visible:
                                    left_panel = download_tab.content.content.controls[0]
                                    download_card = left_panel.content.controls[1]
                                    multi_task_container = download_card.content.content.controls[4]
                                    thread_field = multi_task_container.content.controls[0]
                                    concurrent_field = multi_task_container.content.controls[1]
                                    break
            
            if multi_task_container and thread_field and concurrent_field:
                multi_task_container.visible = self.enable_multi_task
                thread_field.disabled = not self.enable_multi_task
                concurrent_field.disabled = not self.enable_multi_task
                page.update()

        # 创建上传标签页内容
        def create_upload_tab():
            # 上传文件选择
            self.selected_files = []
            
            # 调整文件选择按钮为垂直布局
            file_picker_buttons = ft.Column(
                [
                    ft.ElevatedButton(
                        text="选择单个文件",
                        icon=ft.Icons.FILE_UPLOAD_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.all(10),
                        ),
                        on_click=lambda _: file_picker_single.pick_files(
                            allow_multiple=False
                        ),
                        width=150  # 设置固定宽度
                    ),
                    ft.ElevatedButton(
                        text="选择多个文件",
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.all(10),
                        ),
                        on_click=lambda _: file_picker_multiple.pick_files(
                            allow_multiple=True
                        ),
                        width=150  # 设置固定宽度
                    ),
                    ft.ElevatedButton(
                        text="选择文件夹",
                        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.all(10),
                        ),
                        on_click=lambda _: directory_picker.get_directory_path(),
                        width=150  # 设置固定宽度
                    ),
                ],
                spacing=5,  # 按钮之间的垂直间距
                alignment=ft.MainAxisAlignment.START,
            )

            # 创建一个Container来包装ListView，设置背景色和边框
            selected_files_text = ft.ListView(
                expand=True,  # 允许列表扩展
                height=120,  # 增加文件列表的高度
                spacing=1,
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
                padding=5,
                expand=True  # 允许容器扩展
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
                        # 创建一个容器来包装每个文件名
                        selected_files_text.controls.append(
                            ft.Container(
                                content=ft.Text(
                                    f"• {file.name}",
                                    style=normal_text_style,
                                    size=14,
                                    color=ft.Colors.GREY_700,
                                    selectable=True,  # 允许选择文本
                                    no_wrap=False,  # 允许文本换行
                                    text_align=ft.TextAlign.LEFT,  # 左对齐
                                ),
                                padding=ft.padding.symmetric(vertical=2, horizontal=5),
                                expand=True  # 允许容器扩展以适应父容器宽度
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
                        # 清除上传完成提示
                        self.upload_complete_text.visible = False
                        self.upload_complete_text.update()
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
                                    ft.Container(
                                        content=ft.Text(
                                            f"{indent}• {parts[-1]}",
                                            style=normal_text_style,
                                            size=14,
                                            color=ft.Colors.GREY_700,
                                            selectable=True,  # 允许选择文本
                                            no_wrap=False,  # 允许文本换行
                                            text_align=ft.TextAlign.LEFT,  # 左对齐
                                        ),
                                        padding=ft.padding.symmetric(vertical=2, horizontal=5),
                                        expand=True  # 允许容器扩展以适应父容器宽度
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
                **textfield_style,
                disabled=True  # 默认禁用，随多任务开关联动
            )

            concurrent_field = ft.TextField(
                label="并发任务数",
                value="2",
                hint_text="同时上传的文件数",
                prefix_icon=ft.Icons.COMPARE_ARROWS_ROUNDED,
                **textfield_style,
                disabled=True  # 默认禁用，随多任务开关联动
            )

            # 多任务上传开关
            self.enable_multi_upload = False
            # 多任务参数输入框容器，初始隐藏
            multi_upload_params_container = ft.Container(
                content=ft.Row([
                    threads_field, concurrent_field
                ], spacing=5),
                visible=False
            )
            def toggle_multi_upload(e):
                self.enable_multi_upload = e.control.value
                threads_field.disabled = not self.enable_multi_upload
                concurrent_field.disabled = not self.enable_multi_upload
                multi_upload_params_container.visible = self.enable_multi_upload
                page.update()
            multi_upload_checkbox = ft.Checkbox(
                label="启用多任务上传",
                value=False,
                on_change=toggle_multi_upload,
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
                    if not self.selected_files:
                        self.show_snackbar(page, "请先选择要上传的文件")
                        return
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
                    upload_button.disabled = True
                    upload_button.update()
                    self.add_upload_log("开始上传任务...")
                    self.add_upload_log(f"目标聊天: {chat}")
                    self.add_upload_log(f"线程数: {threads}, 并发数: {concurrent}")
                    self.add_upload_log(f"以照片形式上传: {'是' if upload_as_photo.value else '否'}")
                    self.add_upload_log(f"上传后删除: {'是' if delete_after_upload.value else '否'}")
                    # 启动上传线程，增加多任务参数
                    threading.Thread(
                        target=self._upload_thread,
                        args=(
                            self.selected_files,
                            chat,
                            threads,
                            concurrent,
                            upload_as_photo.value,
                            delete_after_upload.value,
                            page,
                            self.enable_multi_upload  # 新增参数
                        ),
                        daemon=True
                    ).start()
                except Exception as ex:
                    print(f"启动上传任务时出错: {str(ex)}")
                    self.add_upload_log(f"启动上传任务时出错: {str(ex)}")
                    self.show_snackbar(page, f"启动上传任务时出错: {str(ex)}")
                    upload_button.disabled = False
                    upload_button.update()

            # 创建上传按钮和提示文本
            upload_button = ft.ElevatedButton(
                text="开始上传",
                icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                style=button_style,
                on_click=start_upload,
                disabled=True,
                expand=1
            )

            # 添加上传完成提示文本
            self.upload_complete_text = ft.Text(
                value="",
                color=ft.Colors.GREEN,
                size=14,
                weight=ft.FontWeight.W_500,
                visible=False  # 初始时不可见
            )

            # 将按钮和提示文本放在同一行
            upload_button_row = ft.Row(
                [
                    upload_button,
                    self.upload_complete_text
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.START
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
            
            # 上传日志卡片右上角增加复制按钮
            copy_upload_log_button = ft.IconButton(
                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                tooltip="复制全部日志",
                on_click=lambda e: self._copy_upload_logs_to_clipboard(e, page),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.padding.all(8),
                    bgcolor=ft.Colors.BLUE_100,
                    color=ft.Colors.BLUE_700,
                ),
            )
            
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
                                                ft.Row(
                                                    [
                                                        # 左侧按钮区域
                                                        ft.Container(
                                                            content=file_picker_buttons,
                                                            padding=ft.padding.only(right=10)
                                                        ),
                                                        # 右侧文件列表区域
                                                        ft.Column([
                                                            ft.Text("已选择的文件:", style=normal_text_style),
                                                            selected_files_container,
                                                        ], 
                                                        expand=True
                                                        ),
                                                    ],
                                                    spacing=5,
                                                    expand=True
                                                ),
                                            ]),
                                            padding=5
                                        ),
                                        elevation=2,
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                    ft.Container(height=10),
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
                                                ft.Container(height=2),
                                                ft.Row(
                                                    [chat_field],
                                                    spacing=5
                                                ),
                                                ft.Container(height=2),
                                                # 多任务上传开关
                                                ft.Row([
                                                    multi_upload_checkbox
                                                ], spacing=5),
                                                # 多任务参数输入框容器
                                                multi_upload_params_container,
                                                ft.Container(height=2),
                                                ft.Row(
                                                    [upload_as_photo, delete_after_upload],
                                                    spacing=5
                                                ),
                                                ft.Container(height=2),
                                                upload_button_row,
                                            ]),
                                            padding=5
                                        ),
                                        elevation=2,
                                        margin=ft.margin.only(top=5),
                                        surface_tint_color=ft.Colors.WHITE
                                    ),
                                ],
                                spacing=0,
                                expand=True,
                                scroll='auto',  # 让左侧内容整体可滚动
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
                                                        ft.Container(expand=True),
                                                        ft.Text("网络速度:", style=ft.TextStyle(
                                                            size=14,
                                                            weight=ft.FontWeight.W_400,
                                                            color=ft.Colors.GREY_700
                                                        )),
                                                        ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=ft.Colors.GREEN_400),
                                                        self.upload_speed_text
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
                                                        copy_upload_log_button,
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
        tabs = ft.Container(
            content=ft.Stack(
                [
                    ft.Container(
                        content=create_download_tab(),
                        visible=True
                    ),
                    ft.Container(
                        content=create_upload_tab(),
                        visible=False
                    )
                ],
                expand=True
            ),
            expand=True
        )

        def switch_tab(e, index):
            """切换标签页"""
            # 更新内容可见性
            tab_contents = tabs.content.controls
            for i, tab in enumerate(tab_contents):
                tab.visible = (i == index)
            tabs.update()
            
            # 更新按钮样式
            buttons = e.control.parent.controls
            for i, button in enumerate(buttons):
                button.style.bgcolor = {
                    "": ft.Colors.BLUE if i == index else ft.Colors.BLUE_100,
                    "hovered": ft.Colors.BLUE_700,
                }
                button.update()

        # 构建主界面
        page.add(
            ft.Container(
                content=ft.Column(
                    [
                        # 顶部区域 - 包含标题和标签页按钮
                        ft.Container(
                            content=ft.Column([
                                # 标题栏
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Icon(ft.Icons.CLOUD_SYNC_ROUNDED, size=28, color=ft.Colors.BLUE_500),
                                            ft.Text("TDL下载器", style=title_style),
                                            ft.Container(expand=True),
                                            ft.Row(
                                                [
                                                    ft.ElevatedButton(
                                                        text="下载",
                                                        icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                                                        style=ft.ButtonStyle(
                                                            shape=ft.RoundedRectangleBorder(radius=8),
                                                            padding=ft.padding.all(15),
                                                            bgcolor={
                                                                "": ft.Colors.BLUE,
                                                                "hovered": ft.Colors.BLUE_700,
                                                            },
                                                            color=ft.Colors.WHITE,
                                                        ),
                                                        on_click=lambda e: switch_tab(e, 0),
                                                    ),
                                                    ft.ElevatedButton(
                                                        text="上传",
                                                        icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                                                        style=ft.ButtonStyle(
                                                            shape=ft.RoundedRectangleBorder(radius=8),
                                                            padding=ft.padding.all(15),
                                                            bgcolor={
                                                                "": ft.Colors.BLUE_100,
                                                                "hovered": ft.Colors.BLUE_700,
                                                            },
                                                            color=ft.Colors.WHITE,
                                                        ),
                                                        on_click=lambda e: switch_tab(e, 1),
                                                    ),
                                                ],
                                                spacing=10,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.START,
                                        spacing=10,
                                    ),
                                    padding=ft.padding.only(bottom=10)
                                ),
                            ]),
                            bgcolor=ft.Colors.BLUE_50,
                            padding=15,
                            border_radius=ft.border_radius.only(bottom_left=10, bottom_right=10)
                        ),
                        
                        # 主要内容区域
                        ft.Container(
                            content=tabs,
                            expand=True,
                            padding=ft.padding.only(top=15)
                        ),
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
            links_field = None
            threads_field = None
            concurrent_field = None
            multi_task_checkbox = None
            
            # 遍历页面寻找输入框
            for control in e.page.controls:
                if isinstance(control, ft.Container):
                    content_column = control.content
                    if isinstance(content_column, ft.Column):
                        main_content = content_column.controls[1]  # 获取主要内容区域
                        if isinstance(main_content, ft.Container):
                            stack = main_content.content.content  # 获取Stack控件
                            if isinstance(stack, ft.Stack):
                                download_tab = stack.controls[0]  # 获取下载标签页
                                if download_tab.visible:  # 确保是当前可见的标签页
                                    left_panel = download_tab.content.content.controls[0]  # 获取左侧面板
                                    download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                                    card_content = download_card.content.content.controls
                                    links_field = card_content[2].content  # 获取链接输入框
                                    multi_task_checkbox = card_content[3].controls[0]  # 获取多任务下载复选框
                                    multi_task_container = card_content[4]  # 获取多任务设置容器
                                    if multi_task_container.visible:  # 如果多任务设置可见
                                        threads_field = multi_task_container.content.controls[0]  # 获取线程数输入框
                                        concurrent_field = multi_task_container.content.controls[1]  # 获取并发数输入框
                                    break
            
            if not links_field:
                raise Exception("无法找到链接输入框")
            
            links_text = links_field.value.strip()
            if not links_text:
                self.show_snackbar(e.page, "请输入下载链接")
                return
            
            # 获取线程数和并发数（如果启用了多任务下载）
            threads = 1
            concurrent = 1
            if multi_task_checkbox and multi_task_checkbox.value:
                try:
                    threads = int(threads_field.value)
                    concurrent = int(concurrent_field.value)
                    if threads < 1 or concurrent < 1:
                        raise ValueError()
                except:
                    self.show_snackbar(e.page, "线程数和并发数必须是大于0的整数")
                    return
            
            # 分割多行链接
            links = [link.strip() for link in links_text.split("\n") if link.strip()]
            
            # 禁用按钮
            download_button = None
            for control in e.page.controls:
                if isinstance(control, ft.Container):
                    content_column = control.content
                    if isinstance(content_column, ft.Column):
                        main_content = content_column.controls[1]  # 获取主要内容区域
                        if isinstance(main_content, ft.Container):
                            stack = main_content.content.content  # 获取Stack控件
                            if isinstance(stack, ft.Stack):
                                download_tab = stack.controls[0]  # 获取下载标签页
                                if download_tab.visible:  # 确保是当前可见的标签页
                                    left_panel = download_tab.content.content.controls[0]  # 获取左侧面板
                                    download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                                    download_button = download_card.content.content.controls[5].controls[0]  # 获取下载按钮
                                    break
            
            if download_button:
                download_button.disabled = True
                download_button.update()
            
            # 确保下载目录存在
            os.makedirs(self.downloads_dir, exist_ok=True)
            
            # 启动下载线程
            threading.Thread(target=self._download_thread, args=(links, threads, concurrent, e.page), daemon=True).start()
        
        except Exception as ex:
            self.add_log(f"启动下载时出错: {str(ex)}")
            self.show_snackbar(e.page, f"启动下载时出错: {str(ex)}")
    
    def _download_thread(self, links, threads, concurrent, page):
        try:
            # 保存链接和文件名的映射关系
            self.download_links_map.clear()  # 清除旧的映射
            for link in links:
                # 从链接中提取文件名
                filename = link.split('/')[-1].split('?')[0]
                self.download_links_map[filename] = link
                self.add_log(f"记录文件映射: {filename} -> {link}")

            print("开始下载...")  # 调试输出
            self.add_log(f"下载保存目录: {self.downloads_dir}")
            self.add_log(f"下载线程数: {threads}, 并发任务数: {concurrent}")
            
            # 创建批处理文件内容
            batch_content = "@echo off\n"
            batch_content += "chcp 65001\n"  # 设置CMD编码为UTF-8
            batch_content += "set PYTHONIOENCODING=utf-8\n"  # 设置Python输出编码
            
            # 添加环境变量设置命令
            for var_name, var_value in self.env_vars.items():
                batch_content += f"set {var_name}={var_value}\n"
            
            # 添加下载命令
            total_links = len(links)
            
            if self.enable_multi_task:
                # 多任务模式：将所有链接合并到一个命令中
                dl_cmd = f"tdl.exe dl -t {threads} -l {concurrent}"
                for link in links:
                    dl_cmd += f" -u {link}"
                batch_content += f"{dl_cmd}\n"
            else:
                # 单任务模式：每个链接一个命令
                for link in links:
                    dl_cmd = f"tdl.exe dl -u {link}"
                    batch_content += f"{dl_cmd}\n"
            
            self.add_log(f"添加下载命令: {dl_cmd}")
            
            # 创建临时批处理文件
            batch_file = os.path.join(self.base_path, "tdl_download.bat")
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write(batch_content)
            
            self.add_log(f"已创建批处理文件: {batch_file}")
            
            # 执行批处理文件
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'  # 修复Windows下的编码问题
            
            process = subprocess.Popen(
                batch_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=False,  # 改为False以手动处理编码
                shell=True,
                startupinfo=startupinfo,
                env=env
            )
            
            # 将进程添加到列表中
            self.running_processes.append(process)
            
            # 初始化变量
            current_task = None
            
            # 正则表达式模式
            start_pattern = re.compile(rb'Downloading\s+(.+?)\s+to\s+')
            done_pattern = re.compile(rb'(.+?)\s*->\s*.+?\s*done!')
            # 添加系统信息匹配模式
            system_info_pattern = re.compile(rb'CPU: \d+\.\d+% Memory: \d+\.\d+ MB Goroutines: \d+')
            # 添加控制字符匹配模式
            control_chars_pattern = re.compile(rb'\x1b\[[0-9;]*[a-zA-Z]|\[A\[K')
            # 添加进度匹配模式
            progress_pattern = re.compile(rb'(\d+(?:\.\d+)?)%')
            speed_pattern = re.compile(rb'(\d+(?:\.\d+)?)\s*([KMGT]?B)/s')
            
            def decode_bytes(b):
                """解码字节流，优先utf-8，再gbk，最后fallback"""
                try:
                    b = control_chars_pattern.sub(b'', b)
                    # 先尝试utf-8
                    try:
                        return b.decode('utf-8')
                    except UnicodeDecodeError:
                        pass
                    # 再尝试gbk
                    try:
                        return b.decode('gbk')
                    except UnicodeDecodeError:
                        pass
                    # 最后用系统默认
                    try:
                        return b.decode(locale.getpreferredencoding())
                    except UnicodeDecodeError:
                        pass
                    # fallback
                    return b.decode('utf-8', errors='replace')
                except Exception as e:
                    print(f"解码错误: {str(e)}")
                    return b.decode('utf-8', errors='replace')
            
            # 初始化下载状态
            self.reset_download_status()
            total_links = len(links)
            self.total_tasks = total_links
            self.completed_tasks = 0
            
            # 新增多任务正则
            multi_task_progress_pattern = re.compile(rb'(?:Total:)?\s*(\d+(?:\.\d+)?)%')
            multi_task_speed_pattern = re.compile(rb'(\d+(?:\.\d+)?)\s*([KMGT]?B)/s')
            while True:
                try:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        # 处理编码问题
                        line = line.rstrip(b'\r\n')  # 使用二进制模式处理换行符
                        
                        if line:
                            # 跳过系统信息
                            if system_info_pattern.search(line):
                                continue
                            
                            # 检测新任务开始
                            start_match = start_pattern.search(line)
                            if start_match:
                                filename_bytes = start_match.group(1)
                                # 尝试解码文件名
                                current_task = decode_bytes(filename_bytes)
                                # 移除可能的控制字符
                                current_task = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\[A\[K', '', current_task)
                                self.add_log(f"→ 开始下载: {current_task}")
                                continue
                            
                            # 检测任务完成
                            done_match = done_pattern.search(line)
                            if done_match:
                                filename_bytes = done_match.group(1)
                                # 尝试解码文件名
                                filename = decode_bytes(filename_bytes)
                                # 移除可能的控制字符
                                filename = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\[A\[K', '', filename)
                                self.add_log(f"√ 完成下载: {filename}")
                                self.completed_tasks += 1
                                # 更新总进度
                                total_progress = (self.completed_tasks / self.total_tasks) * 100
                                self.update_download_progress(progress=total_progress)
                                continue
                            
                            # 检测进度和速度
                            progress_match = progress_pattern.search(line)
                            speed_match = speed_pattern.search(line)
                            
                            if self.enable_multi_task:
                                # 多任务模式：只解析 [#####....] [6s; 1.49 MB/s] 这种行
                                bar_speed_pattern = re.compile(rb'\[(#+)([\. ]+)\]\s*\[(\d+)s;\s*([\d\.]+)\s*([KMGT]?B)/s\]', re.I)
                                match = bar_speed_pattern.search(line)
                                if match:
                                    bar_count = len(match.group(1))
                                    total_count = bar_count + len(match.group(2))
                                    progress = (bar_count / total_count) * 100 if total_count > 0 else 0
                                    speed_value = float(match.group(4).decode('ascii'))
                                    speed_unit = match.group(5).decode('ascii').upper()
                                    multiplier = {
                                        'B': 1,
                                        'KB': 1024,
                                        'MB': 1024 * 1024,
                                        'GB': 1024 * 1024 * 1024,
                                        'TB': 1024 * 1024 * 1024 * 1024
                                    }.get(speed_unit, 1)
                                    speed_in_bytes = speed_value * multiplier
                                    speed = self._format_speed(speed_in_bytes)
                                    self.update_download_progress(progress=progress, speed=speed)
                                    self.update_network_speed(speed_in_bytes, True)
                                    # 先写日志，再 continue
                                    decoded_line = decode_bytes(line)
                                    decoded_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\[A\[K', '', decoded_line)
                                    self.add_log(decoded_line)
                                    continue
                            else:
                                # 单任务模式：原有逻辑
                                if progress_match or speed_match:
                                    progress = None
                                    speed = None
                                    if progress_match:
                                        current_progress = float(progress_match.group(1))
                                        completed_progress = (self.completed_tasks / self.total_tasks) * 100
                                        current_contribution = (current_progress / 100) * (100 / self.total_tasks)
                                        total_progress = completed_progress + current_contribution
                                        progress = total_progress
                                    if speed_match:
                                        speed_value = float(speed_match.group(1).decode('ascii'))
                                        speed_unit = speed_match.group(2).decode('ascii')
                                        unit = speed_unit.upper()
                                        multiplier = {
                                            'B': 1,
                                            'KB': 1024,
                                            'MB': 1024 * 1024,
                                            'GB': 1024 * 1024 * 1024,
                                            'TB': 1024 * 1024 * 1024 * 1024
                                        }.get(unit, 1)
                                        speed_in_bytes = speed_value * multiplier
                                        self.update_network_speed(speed_in_bytes, True)
                                        speed = self._format_speed(speed_in_bytes)
                                    self.update_download_progress(
                                        progress=progress,
                                        speed=speed
                                    )
                            
                            # 解码当前行
                            decoded_line = decode_bytes(line)
                            # 移除可能的控制字符
                            decoded_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\[A\[K', '', decoded_line)
                            
                            # 如果有当前任务，在输出中添加任务标识
                            if current_task and decoded_line:  # 确保解码后的行不为空
                                # 检查是否包含进度信息
                                if '%' in decoded_line:
                                    self.add_log(f"  [{current_task}] {decoded_line}")
                                else:
                                    self.add_log(f"  {decoded_line}")
                            elif decoded_line:  # 确保解码后的行不为空
                                self.add_log(decoded_line)
                except Exception as e:
                    self.add_log(f"[日志解析错误: {str(e)}]")
                    print(f"Debug - 日志解析错误: {str(e)}")
            
            # 删除临时批处理文件
            try:
                os.remove(batch_file)
                self.add_log("已删除临时批处理文件")
            except:
                self.add_log("无法删除临时批处理文件")
            
            # 检查临时文件
            self.check_temp_files()
            
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
            
            # 完成所有下载，重置状态
            self.reset_download_status()
            self.download_speed_text.value = "0 B/s"
            self.total_progress_bar.value = 0
            self.total_progress_text.value = "0%"
            self.download_speed_text.update()
            self.total_progress_bar.update()
            self.total_progress_text.update()
            
            self.add_log("所有下载任务已完成")
            self.add_log(f"下载文件保存在: {self.downloads_dir}")
            self.add_log("您可以点击「打开下载文件夹」按钮查看下载的文件")
                
        except Exception as e:
            self.add_log(f"发生错误: {str(e)}")
            self.show_snackbar(page, f"发生错误: {str(e)}")
            print(f"Debug - 发生错误: {str(e)}")
        finally:
            try:
                # 尝试在标签页内容中查找下载按钮
                download_button = None
                for control in page.controls:
                    if isinstance(control, ft.Container):
                        content_column = control.content
                        if isinstance(content_column, ft.Column):
                            main_content = content_column.controls[1]  # 获取主要内容区域
                            if isinstance(main_content, ft.Container):
                                stack = main_content.content.content  # 获取Stack控件
                                if isinstance(stack, ft.Stack):
                                    download_tab = stack.controls[0]  # 获取下载标签页
                                    if download_tab.visible:  # 确保是当前可见的标签页
                                        left_panel = download_tab.content.content.controls[0]  # 获取左侧面板
                                        download_card = left_panel.content.controls[1]  # 获取下载设置卡片
                                        download_button = download_card.content.content.controls[5].controls[0]  # 获取下载按钮
                                        break
                
                if download_button:
                    download_button.disabled = False
                    download_button.update()
                else:
                    print("无法找到下载按钮")
            except Exception as e:
                print(f"重新启用下载按钮时出错: {str(e)}")

    def check_temp_files(self):
        """检查并处理临时文件"""
        try:
            self.add_log("\n开始检查临时文件...")
            temp_files = [f for f in os.listdir(self.downloads_dir) if f.endswith('.tmp')]
            
            if not temp_files:
                self.add_log("未发现临时文件")
                return
            
            self.add_log(f"发现 {len(temp_files)} 个临时文件，开始处理...")
            
            # 创建结果记录文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = os.path.join(self.downloads_dir, f"temp_files_process_{timestamp}.txt")
            
            # 用于记录处理结果的列表
            process_results = []
            process_results.append(f"临时文件处理记录 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            process_results.append(f"发现 {len(temp_files)} 个临时文件\n")
            
            for temp_file in temp_files:
                temp_path = os.path.join(self.downloads_dir, temp_file)
                file_size = os.path.getsize(temp_path)
                
                if file_size > 0:
                    try:
                        # 获取不带.tmp的文件名
                        original_filename = temp_file[:-4]  # 移除.tmp后缀
                        new_path = os.path.join(self.downloads_dir, original_filename)
                        
                        # 重命名文件
                        os.rename(temp_path, new_path)
                        
                        # 查找并记录对应的下载链接
                        original_link = None
                        for filename, link in self.download_links_map.items():
                            if filename in original_filename:  # 使用in而不是完全匹配，因为文件名可能有额外的数字等
                                original_link = link
                                break
                        
                        # 记录处理结果
                        result_entry = f"文件: {temp_file} -> {original_filename}"
                        if original_link:
                            result_entry += f"\n下载链接: {original_link}"
                            self.add_log(f"已恢复临时文件: {temp_file} -> {original_filename}")
                            self.add_log(f"对应的下载链接: {original_link}")
                        else:
                            result_entry += "\n下载链接: 未找到对应链接"
                            self.add_log(f"已恢复临时文件: {temp_file} -> {original_filename}")
                            self.add_log("无法找到对应的下载链接")
                        
                        result_entry += f"\n文件大小: {self._format_file_size(file_size)}\n"
                        process_results.append(result_entry)
                        
                    except Exception as e:
                        error_msg = f"处理临时文件 {temp_file} 时出错: {str(e)}"
                        self.add_log(error_msg)
                        process_results.append(f"错误: {error_msg}\n")
                else:
                    skip_msg = f"跳过空临时文件: {temp_file}"
                    self.add_log(skip_msg)
                    process_results.append(f"{skip_msg}\n")
            
            # 写入处理结果到文件
            try:
                with open(result_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(process_results))
                self.add_log(f"处理结果已保存到文件: {result_file}")
            except Exception as e:
                self.add_log(f"保存处理结果到文件时出错: {str(e)}")
            
            self.add_log("临时文件处理完成\n")
            
        except Exception as e:
            self.add_log(f"检查临时文件时出错: {str(e)}")
    
    def _format_file_size(self, size_in_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"

    def _format_speed(self, speed_in_bytes):
        """格式化网络速度显示
        Args:
            speed_in_bytes: 字节每秒的速度
        Returns:
            格式化后的速度字符串
        """
        if speed_in_bytes < 1024:
            return f"{speed_in_bytes:.2f} B/s"
        elif speed_in_bytes < 1024 * 1024:
            return f"{speed_in_bytes/1024:.2f} KB/s"
        elif speed_in_bytes < 1024 * 1024 * 1024:
            return f"{speed_in_bytes/(1024*1024):.2f} MB/s"
        else:
            return f"{speed_in_bytes/(1024*1024*1024):.2f} GB/s"

    def update_network_speed(self, speed_in_bytes, is_download=True):
        """更新网络速度显示
        Args:
            speed_in_bytes: 字节每秒的速度
            is_download: 是否为下载速度
        """
        try:
            formatted_speed = self._format_speed(speed_in_bytes)
            if is_download:
                self.current_download_speed = formatted_speed
                if self.download_speed_text:
                    self.download_speed_text.value = formatted_speed
                    self.download_speed_text.update()
            else:
                self.current_upload_speed = formatted_speed
                if self.upload_speed_text:
                    self.upload_speed_text.value = formatted_speed
                    self.upload_speed_text.update()
        except Exception as e:
            print(f"更新网络速度显示时出错: {str(e)}")

    def _upload_thread(self, files, chat, threads, concurrent, as_photo, delete_after, page, enable_multi_upload=False):
        try:
            last_bytes = 0
            last_time = time.time()
            self.update_upload_progress(current_value=0, total_value=0, text="准备上传")
            self.upload_complete_text.visible = False
            self.upload_complete_text.update()
            batch_content = "@echo off\n"
            batch_content += "chcp 65001\n"
            batch_content += "set PYTHONIOENCODING=utf-8\n"
            for var_name, var_value in self.env_vars.items():
                batch_content += f"set {var_name}={var_value}\n"
            total_files = len(files)
            if enable_multi_upload:
                # 多任务上传：合并所有文件为一个命令
                up_cmd = f"tdl.exe up -t {threads} -l {concurrent} -c {chat}"
                for file in files:
                    up_cmd += f" -p \"{file.path}\""
                if as_photo:
                    up_cmd += " --photo"
                if delete_after:
                    up_cmd += " --rm"
                batch_content += f"echo [TDLGUI_MARKER] 开始上传 1/{total_files}: 多任务\n"
                batch_content += f"{up_cmd}\n"
                batch_content += f"echo [TDLGUI_MARKER] 完成上传 1/{total_files}\n"
                self.add_upload_log(f"添加上传命令: {up_cmd}")
            else:
                # 单任务上传：每个文件单独命令
                for i, file in enumerate(files):
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
            batch_file = os.path.join(self.base_path, "tdl_upload.bat")
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
                filled = int(progress_bar_width * progress / 100)
                bar = '█' * filled + '░' * (progress_bar_width - filled)
                return f"[{bar}] {progress:.1f}%"
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    try:
                        if isinstance(line, bytes):
                            line = line.decode('utf-8', errors='replace')
                        line = line.strip()
                        # 检测我们的特殊标记
                        if "[TDLGUI_MARKER] 开始上传" in line:
                            last_bytes = 0
                            last_time = time.time()
                            self.update_network_speed(0, False)
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
                            else:
                                # 多任务上传时，file_name为"多任务"
                                is_uploading = True
                                current_progress_line = f"正在多任务上传 ({current_file_index+1}/{total_files})\n{make_progress_bar(0)}"
                                self.add_upload_log(current_progress_line)
                                self.update_upload_progress(
                                    current_value=0,
                                    text=f"多任务上传 {current_file_index+1}/{total_files}"
                                )
                                total_progress = (completed_files / total_files) * 100
                                self.update_upload_progress(total_value=total_progress)
                                last_progress = 0
                        elif "[TDLGUI_MARKER] 完成上传" in line:
                            self.update_network_speed(0, False)
                            completed_files += 1
                            is_uploading = False
                            if current_progress_line:
                                final_progress = f"{current_progress_line.splitlines()[0]}\n{make_progress_bar(100)} - 完成"
                                self.add_upload_log(final_progress, replace_last=True)
                                current_progress_line = None
                            self.update_upload_progress(current_value=100)
                            total_progress = (completed_files / total_files) * 100
                            self.update_upload_progress(total_value=total_progress)
                            last_progress = 100
                        elif is_uploading:
                            # 多任务上传时，解析整体进度和速度
                            if enable_multi_upload:
                                # 解析如 [#####....] [6s; 1.49 MB/s] 这种行
                                bar_speed_pattern = re.compile(r'\[(#+)([\. ]+)\]\s*\[(\d+)s;\s*([\d\.]+)\s*([KMGT]?B)/s\]', re.I)
                                match = bar_speed_pattern.search(line)
                                if match:
                                    bar_count = len(match.group(1))
                                    total_count = bar_count + len(match.group(2))
                                    progress = (bar_count / total_count) * 100 if total_count > 0 else 0
                                    speed_value = float(match.group(4))
                                    speed_unit = match.group(5).upper()
                                    multiplier = {
                                        'B': 1,
                                        'KB': 1024,
                                        'MB': 1024 * 1024,
                                        'GB': 1024 * 1024 * 1024,
                                        'TB': 1024 * 1024 * 1024 * 1024
                                    }.get(speed_unit, 1)
                                    speed_in_bytes = speed_value * multiplier
                                    self.update_network_speed(speed_in_bytes, False)
                                    progress_text = f"{current_progress_line.splitlines()[0]}\n{make_progress_bar(progress)}"
                                    self.add_upload_log(progress_text, replace_last=True)
                                    self.update_upload_progress(current_value=progress)
                                    total_progress = progress
                                    self.update_upload_progress(total_value=total_progress)
                                    last_progress = progress
                                    continue
                            # 单任务上传原有逻辑
                            speed_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMGT]?B)/s', line, re.IGNORECASE)
                            if speed_match:
                                value = float(speed_match.group(1))
                                unit = speed_match.group(2).upper()
                                multiplier = {
                                    'B': 1,
                                    'KB': 1024,
                                    'MB': 1024 * 1024,
                                    'GB': 1024 * 1024 * 1024,
                                    'TB': 1024 * 1024 * 1024 * 1024
                                }.get(unit, 1)
                                speed_in_bytes = value * multiplier
                                self.update_network_speed(speed_in_bytes, False)
                            progress_match = re.search(r'(\d+\.\d+)%', line)
                            if progress_match and current_progress_line:
                                file_progress = float(progress_match.group(1))
                                progress_text = f"{current_progress_line.splitlines()[0]}\n{make_progress_bar(file_progress)}"
                                self.add_upload_log(progress_text, replace_last=True)
                                self.update_upload_progress(current_value=file_progress)
                                total_progress = ((completed_files + file_progress / 100) / total_files) * 100
                                self.update_upload_progress(total_value=total_progress)
                                last_progress = file_progress
                            elif not progress_match and not line.startswith("[TDLGUI_MARKER]"):
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
            self.add_upload_log("所有上传任务已完成")
            
            # 显示完成提示
            self.upload_complete_text.value = "上传已完成，继续上传请重新选择文件"
            self.upload_complete_text.visible = True
            self.upload_complete_text.update()
                
        except Exception as e:
            self.add_upload_log(f"发生错误: {str(e)}")
            self.show_snackbar(page, f"发生错误: {str(e)}")
        finally:
            try:
                # 尝试在标签页内容中查找上传按钮
                tabs = page.controls[0].content.controls[1]  # 获取标签页控件
                upload_tab = tabs.tabs[1].content  # 获取上传标签页内容
                upload_settings_card = upload_tab.content.controls[0].content.controls[1]  # 获取上传设置卡片
                upload_button = upload_settings_card.content.content.controls[-1].controls[0]  # 获取上传按钮
                
                # 重新启用按钮
                upload_button.disabled = False
                upload_button.update()
            except Exception as e:
                #print(f"重新启用上传按钮时出错: {str(e)}")
                pass

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

    def reset_download_status(self):
        """重置下载状态显示"""
        try:
            self.download_speed_text.value = "0 B/s"
            self.total_tasks = 0
            self.completed_tasks = 0
            self.current_task_progress = 0
            self.total_progress_bar.value = 0
            self.total_progress_text.value = "0%"
            self.download_speed_text.update()
            self.total_progress_bar.update()
            self.total_progress_text.update()
        except Exception as e:
            print(f"重置下载状态时出错: {str(e)}")

    def update_download_progress(self, progress=None, speed=None):
        """更新下载进度显示"""
        try:
            # 更新进度
            if progress is not None:
                # 更新进度条
                self.total_progress_bar.value = progress / 100
                self.total_progress_text.value = f"{progress:.1f}%"
                self.total_progress_bar.update()
                self.total_progress_text.update()
            
            # 更新速度显示
            if speed is not None:
                self.download_speed_text.value = speed
                self.download_speed_text.update()
            
        except Exception as e:
            print(f"更新下载进度显示时出错: {str(e)}")

    def _copy_logs_to_clipboard(self, e, page):
        """一键复制所有下载日志到剪贴板"""
        try:
            logs = []
            for c in self.log_view.controls:
                if hasattr(c, 'content') and hasattr(c.content, 'value'):
                    logs.append(str(c.content.value))
            all_logs = '\n'.join(logs)
            page.set_clipboard(all_logs)
            self.show_snackbar(page, "日志已复制到剪贴板！")
        except Exception as ex:
            self.show_snackbar(page, f"复制失败: {ex}")

    # 新增上传日志复制方法
    def _copy_upload_logs_to_clipboard(self, e, page):
        try:
            logs = []
            for c in self.upload_log_view.controls:
                if hasattr(c, 'content') and hasattr(c.content, 'value'):
                    logs.append(str(c.content.value))
            all_logs = '\n'.join(logs)
            page.set_clipboard(all_logs)
            self.show_snackbar(page, "上传日志已复制到剪贴板！")
        except Exception as ex:
            self.show_snackbar(page, f"复制失败: {ex}")

if __name__ == "__main__":
    app = TDLDownloaderApp()
    ft.app(target=app.main) 